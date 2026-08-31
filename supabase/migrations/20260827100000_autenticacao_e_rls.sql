-- Fase 3: identidade e autorização no banco.
--
-- Três coisas:
--   1. a foreign key para `auth.users`, adiada da Fase 1
--   2. Row Level Security nas três tabelas
--   3. privilégios: `authenticated` lê o que é seu e não escreve nada
--
-- ATÉ ONDE A RLS PROTEGE. O backend conecta como dono do banco, e dono ignora
-- RLS. Portanto ela **não** é uma rede contra bug de roteamento na API — quem
-- cobre isso é `get_conta_do_cliente`, com um teste por rota. O que a RLS
-- protege é o acesso **direto** ao banco: PostgREST, Studio, ou qualquer cliente
-- de posse da chave anônima. Essa superfície existe e é exposta na porta 54321.

-- ------------------------------------------------------------------- FK ----
-- Adiada da F1 porque `auth.users` só ganha formato final depois que o GoTrue
-- roda as próprias migrações, e amarrar a persistência a isso tornaria a Fase 1
-- impossível de testar sem a stack de autenticação no ar.
alter table clientes
  add constraint clientes_auth_user_fk
  foreign key (auth_user_id) references auth.users(id) on delete restrict;

-- ------------------------------------------------------- cliente corrente ---
create or replace function cliente_atual() returns bigint
language sql stable security definer set search_path = public, auth as $$
  select id from clientes where auth_user_id = auth.uid();
$$;

comment on function cliente_atual is
  'Resolve auth.uid() para clientes.id. Usada pelas policies de RLS.';

-- ------------------------------------------------------------------ RLS ----
alter table clientes   enable row level security;
alter table contas     enable row level security;
alter table transacoes enable row level security;

-- Nenhuma policy de insert, update ou delete: escrita é exclusividade das
-- funções de movimentação, que o backend invoca como dono.
create policy cliente_le_a_si_mesmo on clientes
  for select to authenticated
  using (auth_user_id = (select auth.uid()));

create policy cliente_le_suas_contas on contas
  for select to authenticated
  using (cliente_id = (select cliente_atual()));

create policy cliente_le_suas_transacoes on transacoes
  for select to authenticated
  using (conta_id in (select id from contas where cliente_id = (select cliente_atual())));

-- ----------------------------------------------------------- privilégios ---
grant usage on schema public to authenticated;
grant select on clientes, contas, transacoes to authenticated;

-- Explícito, embora já seja o padrão: escrever nessas tabelas nunca é
-- prerrogativa de quem chega pela chave anônima.
revoke insert, update, delete, truncate on clientes, contas, transacoes
  from authenticated, anon;
revoke select on clientes, contas, transacoes from anon;

-- As funções de movimentação NÃO são expostas a `authenticated`. Elas não
-- verificam titularidade por conta própria — quem verifica é a API — então
-- concedê-las permitiria a qualquer portador de token depositar e sacar em
-- conta alheia passando o id pela RPC do PostgREST.
revoke execute on function realizar_deposito(bigint, numeric) from public, anon, authenticated;
revoke execute on function realizar_saque(bigint, numeric)    from public, anon, authenticated;
revoke execute on function transferir(bigint, bigint, numeric) from public, anon, authenticated;
revoke execute on function abrir_conta(bigint, text, text, int) from public, anon, authenticated;
revoke execute on function encerrar_conta(bigint)              from public, anon, authenticated;

-- A view de reconciliação expõe todas as contas: é ferramenta de operação.
revoke select on contas_divergentes from anon, authenticated;
