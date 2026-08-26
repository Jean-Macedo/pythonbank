-- Schema inicial: clientes, contas e o ledger de transações.
-- Ver docs/02-modelo-de-dados.md
--
-- Um cliente possui N contas. O saldo é coluna mantida por desempenho, mas a
-- verdade é a tabela `transacoes` (DT-03): as duas escritas acontecem sempre na
-- mesma transação, garantido pelas funções da migração seguinte.

-- ---------------------------------------------------------------- clientes --
-- `auth_user_id` guarda a identidade, mas SEM foreign key para `auth.users`
-- nesta fase. A tabela do GoTrue só ganha seu formato final quando o serviço de
-- autenticação roda as próprias migrações, e amarrar a persistência a isso
-- tornaria a Fase 1 impossível de testar sem a stack de auth no ar.
-- A constraint entra na Fase 3, junto com o resto da autenticação.
create table clientes (
  id              bigint generated always as identity primary key,
  auth_user_id    uuid not null unique,
  nome            text not null check (length(trim(nome)) > 0),
  cpf             char(11) not null unique check (cpf ~ '^[0-9]{11}$'),
  email           text not null,
  telefone        text not null check (telefone ~ '^[0-9]{10,11}$'),
  data_nascimento date not null check (data_nascimento <= current_date),
  data_cadastro   timestamptz not null default now()
);

comment on table clientes is
  'Titulares. `cpf` tem formato garantido aqui e dígitos verificadores validados no domínio Python.';

-- ------------------------------------------------------ numeração de contas --
-- RN-1.8: quem numera é o banco. Duas aberturas simultâneas não podem colidir,
-- e uma sequence é a única forma de garantir isso sem serializar a aplicação.
create sequence contas_numero_seq start 100001;

create or replace function gerar_numero_conta() returns text
language sql volatile as $$
  select lpad(nextval('contas_numero_seq')::text, 8, '0');
$$;

-- ------------------------------------------------------------------ contas --
create table contas (
  id         bigint generated always as identity primary key,
  cliente_id bigint not null references clientes(id) on delete restrict,
  agencia    char(4) not null default '0001' check (agencia ~ '^[0-9]{4}$'),
  numero     text    not null default gerar_numero_conta(),
  tipo       text    not null check (tipo in ('corrente','poupanca')),
  apelido    text    check (apelido is null or length(trim(apelido)) > 0),
  saldo      numeric(15,2) not null default 0 check (saldo >= 0),
  ativa      boolean not null default true,
  aberta_em  timestamptz not null default now(),

  unique (agencia, numero)
);

-- espelha `Cliente._exigir_apelido_livre`: único por cliente, ignorando caixa
create unique index contas_apelido_idx
    on contas (cliente_id, lower(apelido))
 where apelido is not null;

create index contas_cliente_idx on contas (cliente_id) where ativa;

comment on column contas.saldo is
  'Cache do ledger. Só alterado dentro da mesma transação que insere em `transacoes`.';

-- -------------------------------------------------------------- transacoes --
create table transacoes (
  id             bigint generated always as identity primary key,
  conta_id       bigint not null references contas(id) on delete restrict,
  tipo           text not null check (tipo in
                   ('deposito','saque','transferencia_saida','transferencia_entrada')),
  valor          numeric(15,2) not null check (valor > 0),
  saldo_apos     numeric(15,2) not null check (saldo_apos >= 0),
  contraparte_id bigint references contas(id),
  data_hora      timestamptz not null default now(),

  -- contraparte existe se e somente se for transferência
  constraint contraparte_coerente check (
    (tipo in ('transferencia_saida','transferencia_entrada')) = (contraparte_id is not null)
  )
);

-- ordenação do extrato: (data_hora, id) desc, que é também a chave do cursor
create index transacoes_extrato_idx on transacoes (conta_id, data_hora desc, id desc);

comment on table transacoes is
  'Ledger append-only. Correção é lançamento de sinal oposto, nunca update ou delete.';

-- ------------------------------------------------------------ integridade ---
-- O ledger não pode ser reescrito: só a role de serviço insere, e ninguém
-- atualiza ou apaga. As policies de RLS entram na Fase 3; esta regra é anterior
-- a qualquer autorização e vale inclusive para o backend.
create or replace function impedir_reescrita_do_ledger() returns trigger
language plpgsql as $$
begin
  raise exception 'LEDGER_IMUTAVEL';
end; $$;

create trigger transacoes_sem_update
  before update or delete on transacoes
  for each row execute function impedir_reescrita_do_ledger();
