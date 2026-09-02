"""Banco separado para os testes de integração.

**Por que existe.** Os testes escreviam no mesmo banco usado no desenvolvimento
e truncavam tabelas a cada caso. Quem estivesse com a aplicação aberta perdia as
contas que tinha criado — e, antes de uma correção anterior, o cadastro inteiro.
Rodar a suíte não pode destruir o trabalho de ninguém.

**Por que só os testes de integração.** Eles falam SQL direto e não precisam do
GoTrue. Os de API precisam de JWT assinado de verdade, e o GoTrue escreve em
`auth.users` do banco principal; como o PostgreSQL não faz foreign key entre
bancos, movê-los quebraria o cadastro. Aqueles limpam apenas os próprios dados.

**O esboço de `auth`.** As migrações referenciam `auth.users` e `auth.uid()`,
que aqui não existem — não há GoTrue neste banco. O esboço abaixo cria o mínimo
para as migrações aplicarem sem alteração: é isso que garante que o schema
testado seja o mesmo que roda em produção.
"""

import pathlib

import psycopg
from psycopg import sql

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MIGRACOES = RAIZ / "supabase" / "migrations"

BANCO_DE_TESTE = "banco_jean_teste"

#: Mínimo que as migrações esperam encontrar no schema `auth`.
ESBOCO_AUTH = """
create schema if not exists auth;

create table if not exists auth.users (
  id    uuid primary key,
  email text
);

-- Lê a claim que a sessão declarar, como o `auth.uid()` do Supabase faz.
-- Os testes de RLS definem `request.jwt.claims` para exercitar as policies.
create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(
    current_setting('request.jwt.claims', true)::json->>'sub', ''
  )::uuid;
$$;

-- Papéis do Supabase. Existem no cluster quando o `supabase start` rodou, mas
-- criá-los aqui torna o banco de teste utilizável em qualquer PostgreSQL.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
end $$;
"""


def dsn_de(dsn_base: str, banco: str) -> str:
    """Troca o nome do banco no DSN, preservando credenciais e host."""
    base, _, _ = dsn_base.rpartition("/")
    return f"{base}/{banco}"


def _existe(con: psycopg.Connection, banco: str) -> bool:
    return (
        con.execute("select 1 from pg_database where datname = %s", (banco,)).fetchone()
        is not None
    )


def preparar(dsn_base: str, recriar: bool = False) -> str:
    """Garante que o banco de teste existe, migrado e vazio. Devolve o DSN dele.

    Idempotente: chamadas seguintes só confirmam que já está pronto, o que faz a
    suíte custar o preparo uma vez por máquina, e não a cada execução.
    """
    dsn_teste = dsn_de(dsn_base, BANCO_DE_TESTE)

    with psycopg.connect(dsn_base, autocommit=True) as con:
        if recriar and _existe(con, BANCO_DE_TESTE):
            # encerra conexões pendentes antes de derrubar
            con.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity "
                "where datname = %s and pid <> pg_backend_pid()",
                (BANCO_DE_TESTE,),
            )
            con.execute(
                sql.SQL("drop database {}").format(sql.Identifier(BANCO_DE_TESTE))
            )

        if not _existe(con, BANCO_DE_TESTE):
            con.execute(
                sql.SQL("create database {}").format(sql.Identifier(BANCO_DE_TESTE))
            )
            criado = True
        else:
            criado = False

    if criado:
        aplicar_schema(dsn_teste)

    return dsn_teste


def aplicar_schema(dsn_teste: str) -> None:
    """Esboço de `auth` e, na sequência, as migrações reais — sem adaptação.

    Aplicar os mesmos arquivos que vão para produção é o que dá valor ao teste:
    um schema mantido à parte divergiria em silêncio.
    """
    with psycopg.connect(dsn_teste, autocommit=True) as con:
        con.execute(ESBOCO_AUTH)
        for arquivo in sorted(MIGRACOES.glob("*.sql")):
            con.execute(arquivo.read_text(encoding="utf-8"))


def esta_migrado(dsn_teste: str) -> bool:
    with psycopg.connect(dsn_teste, autocommit=True) as con:
        return (
            con.execute("select to_regclass('public.transacoes')").fetchone()[0]
            is not None
        )
