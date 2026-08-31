-- Dados de desenvolvimento (RNF-1.5).
--
-- Dois clientes com três contas no total. O segundo cliente existe para o teste
-- de isolamento da Fase 3: token do cliente A não pode alcançar conta do B.
--
-- Rodado automaticamente por `supabase db reset`.

-- Os CPFs abaixo têm dígitos verificadores válidos — os mesmos usados em
-- tests/conftest.py, para que os dois ambientes falem dos mesmos dados.

-- Usuários do GoTrue. Desde a Fase 3 existe foreign key de `clientes` para
-- `auth.users`, então eles precisam existir antes.
--
-- Só colunas presentes na versão base do schema `auth`: o seed roda durante o
-- "Initialising schema", **antes** de o GoTrue subir e aplicar as próprias
-- migrações. Colunas como `email_confirmed_at` ainda não existem nesse momento.
-- Estes usuários servem para navegar no Studio; quem precisa autenticar de fato
-- cria a conta pela API do GoTrue, que é o caminho real.
insert into auth.users (id, instance_id, aud, role, email, encrypted_password)
values
  ('11111111-1111-1111-1111-111111111111',
   '00000000-0000-0000-0000-000000000000',
   'authenticated', 'authenticated', 'jean@seed.invalid', ''),
  ('22222222-2222-2222-2222-222222222222',
   '00000000-0000-0000-0000-000000000000',
   'authenticated', 'authenticated', 'maria@seed.invalid', '');

insert into clientes (auth_user_id, nome, cpf, email, telefone, data_nascimento) values
  ('11111111-1111-1111-1111-111111111111', 'Jean Macedo',
   '52998224725', 'jean@seed.invalid',  '11987654321', '1995-03-10'),
  ('22222222-2222-2222-2222-222222222222', 'Maria Souza',
   '11144477735', 'maria@seed.invalid', '21998765432', '1988-11-22');

-- Jean tem duas contas; Maria tem uma. A segunda conta do Jean é o que torna
-- possível exercitar transferência entre contas do mesmo titular.
insert into contas (cliente_id, tipo, apelido) values
  ((select id from clientes where cpf = '52998224725'), 'corrente', 'Dia a dia'),
  ((select id from clientes where cpf = '52998224725'), 'poupanca', 'Reserva'),
  ((select id from clientes where cpf = '11144477735'), 'corrente', 'Principal');

-- Saldo inicial pelas funções, não por update direto: assim o seed também
-- exercita o caminho real e o ledger nasce coerente com o saldo (CA-02).
select realizar_deposito(
  (select c.id from contas c
     join clientes cl on cl.id = c.cliente_id
    where cl.cpf = '52998224725' and c.apelido = 'Dia a dia'),
  1500.00
);

select realizar_deposito(
  (select c.id from contas c
     join clientes cl on cl.id = c.cliente_id
    where cl.cpf = '52998224725' and c.apelido = 'Reserva'),
  8400.35
);

select realizar_deposito(
  (select c.id from contas c
     join clientes cl on cl.id = c.cliente_id
    where cl.cpf = '11144477735' and c.apelido = 'Principal'),
  320.00
);
