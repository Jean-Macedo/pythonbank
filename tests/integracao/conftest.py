"""Infraestrutura dos testes de integração.

Rodam contra um **banco separado** (`banco_jean_teste`), criado e migrado
automaticamente na primeira execução. Antes rodavam no banco de desenvolvimento
e truncavam tabelas a cada caso, o que destruía as contas de quem estivesse com
a aplicação aberta.

O schema aplicado é o mesmo de produção, arquivo por arquivo — ver
`tests/banco_de_teste.py`.
"""

import os

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg não instalado")

from tests import banco_de_teste  # noqa: E402

#: Banco de desenvolvimento. Usado só para criar o de teste ao lado dele.
DSN_BASE = os.environ.get(
    "BANCO_TESTE_DSN", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)

#: Preenchido pela fixture de sessão; é onde os testes de fato escrevem.
DSN = banco_de_teste.dsn_de(DSN_BASE, banco_de_teste.BANCO_DE_TESTE)

AUTH_JEAN = "11111111-1111-1111-1111-111111111111"
AUTH_MARIA = "22222222-2222-2222-2222-222222222222"


def conectar():
    return psycopg.connect(DSN, autocommit=True, connect_timeout=5)


@pytest.fixture(scope="session", autouse=True)
def exigir_banco():
    """Cria o banco de teste se ainda não existir, e o migra.

    Idempotente: em execuções seguintes só confirma que está pronto.
    """
    try:
        banco_de_teste.preparar(DSN_BASE)
    except psycopg.OperationalError as erro:
        pytest.skip(
            f"PostgreSQL indisponível em {DSN_BASE}. Rode `supabase start`. ({erro})"
        )

    if not banco_de_teste.esta_migrado(DSN):
        # banco existia mas sem schema — provável interrupção de uma criação
        banco_de_teste.aplicar_schema(DSN)


@pytest.fixture(scope="session", autouse=True)
def titulares(exigir_banco):
    """Os dois titulares de teste, criados uma vez por sessão.

    Existem em `auth.users` porque a foreign key exige — aqui é o esboço, não o
    GoTrue. O segundo titular serve aos testes que precisam de dono diferente.
    """
    with conectar() as con:
        con.execute(
            """
            insert into auth.users (id, email) values
              (%s, 'jean@teste.invalid'), (%s, 'maria@teste.invalid')
            on conflict (id) do nothing
            """,
            (AUTH_JEAN, AUTH_MARIA),
        )
        con.execute(
            """
            insert into clientes (auth_user_id, nome, cpf, email, telefone,
                                  data_nascimento)
            values (%s, 'Jean Macedo', '52998224725', 'jean@teste.invalid',
                    '11987654321', '1995-03-10'),
                   (%s, 'Maria Souza', '11144477735', 'maria@teste.invalid',
                    '21998765432', '1988-11-22')
            on conflict (auth_user_id) do nothing
            """,
            (AUTH_JEAN, AUTH_MARIA),
        )


@pytest.fixture
def banco():
    with conectar() as con:
        yield con


@pytest.fixture(autouse=True)
def base_limpa(banco, titulares):
    """Zera contas e lançamentos entre os casos.

    `truncate` aqui é seguro: o banco é exclusivo dos testes. Ele dispara apenas
    gatilhos de statement, então passa pelo `transacoes_sem_update`, que é
    `for each row` — um `delete` seria recusado, e é exatamente essa a garantia
    de imutabilidade do ledger.
    """
    banco.execute("truncate transacoes, contas restart identity cascade")
    yield


@pytest.fixture
def cliente_id(banco):
    return banco.execute(
        "select id from clientes where auth_user_id = %s", (AUTH_JEAN,)
    ).fetchone()[0]


@pytest.fixture
def abrir(banco, cliente_id):
    """Devolve uma função que abre conta e retorna o id."""

    def _abrir(tipo="corrente", apelido=None, saldo=None):
        conta_id = banco.execute(
            "select (abrir_conta(%s, %s, %s)).id", (cliente_id, tipo, apelido)
        ).fetchone()[0]
        if saldo is not None:
            banco.execute("select realizar_deposito(%s, %s)", (conta_id, saldo))
        return conta_id

    return _abrir


@pytest.fixture
def saldo(banco):
    def _saldo(conta_id):
        return banco.execute(
            "select saldo from contas where id = %s", (conta_id,)
        ).fetchone()[0]

    return _saldo


@pytest.fixture
def divergentes(banco):
    """CA-02 — deve devolver lista vazia sempre."""

    def _divergentes():
        return banco.execute("select * from contas_divergentes").fetchall()

    return _divergentes
