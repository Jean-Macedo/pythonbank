"""Infraestrutura dos testes de integração.

Rodam contra o Supabase local (DT-06). Se o banco não estiver no ar, a suíte
inteira é pulada com uma mensagem explicando o porquê — assim `pytest` continua
funcionando em uma máquina sem Docker, e só os testes de domínio rodam.
"""

import os

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg não instalado")

# Credenciais padrão do `supabase start`. O banco local é descartável e as
# credenciais são fixas e públicas — por isso podem viver no código.
DSN = os.environ.get(
    "BANCO_TESTE_DSN", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)

AUTH_JEAN = "11111111-1111-1111-1111-111111111111"
AUTH_MARIA = "22222222-2222-2222-2222-222222222222"


def conectar():
    return psycopg.connect(DSN, autocommit=True, connect_timeout=5)


@pytest.fixture(scope="session", autouse=True)
def exigir_banco():
    try:
        with conectar() as con:
            con.execute("select 1")
    except psycopg.OperationalError as erro:
        pytest.skip(
            f"Supabase local indisponível em {DSN}. Rode `supabase start`. ({erro})"
        )


@pytest.fixture
def banco():
    with conectar() as con:
        yield con


@pytest.fixture(autouse=True)
def base_limpa(banco):
    """Zera contas e lançamentos, preservando os titulares.

    **`clientes` não é truncada de propósito.** Ela era, e isso destruía o
    cadastro de quem estivesse usando a aplicação enquanto os testes rodavam: o
    usuário do GoTrue sobrevive à truncagem, o titular não, e a sessão passa a
    responder CADASTRO_INCOMPLETO sem que a pessoa tenha feito nada.

    O titular de teste é criado sob demanda e sempre o mesmo, identificado pelo
    `auth_user_id` fixo do seed.

    `truncate` dispara apenas gatilhos de statement, então passa pelo
    `transacoes_sem_update`, que é `for each row`. Um `delete` seria recusado —
    e é exatamente essa a garantia de imutabilidade do ledger.
    """
    banco.execute("truncate transacoes, contas restart identity cascade")
    banco.execute(
        """
        insert into clientes (auth_user_id, nome, cpf, email, telefone, data_nascimento)
        values (%s, 'Jean Macedo', '52998224725', 'jean@seed.invalid',
                '11987654321', '1995-03-10')
        on conflict (auth_user_id) do nothing
        """,
        (AUTH_JEAN,),
    )
    yield


@pytest.fixture
def cliente_id(banco):
    """O titular de teste, não "o primeiro que aparecer".

    `limit 1` sem filtro pegaria o cadastro de outra pessoa quando o banco de
    desenvolvimento tem gente de verdade nele.
    """
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
