"""Testes da API contra o banco real.

Não uso banco falso: o valor destes testes está justamente em verificar a
tradução entre HTTP, domínio e PostgreSQL. Um repositório dublê testaria só o
FastAPI conversando consigo mesmo.
"""

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg não instalado")

from fastapi.testclient import TestClient  # noqa: E402

from tests.integracao.conftest import DSN, conectar  # noqa: E402

AUTH_JEAN = "11111111-1111-1111-1111-111111111111"
AUTH_MARIA = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="session", autouse=True)
def exigir_banco():
    try:
        with conectar() as con:
            con.execute("select 1")
    except psycopg.OperationalError as erro:
        pytest.skip(
            f"Supabase local indisponível em {DSN}. Rode `supabase start`. ({erro})"
        )


@pytest.fixture(scope="session")
def cliente_http():
    from backend.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def banco():
    with conectar() as con:
        yield con


@pytest.fixture(autouse=True)
def base_limpa(banco):
    """Dois clientes: Jean com duas contas, Maria com uma.

    A conta da Maria existe para o teste de titularidade — sem um segundo dono,
    não há como provar que a verificação funciona.
    """
    banco.execute("truncate transacoes, contas, clientes restart identity cascade")
    banco.execute(
        """
        insert into clientes (auth_user_id, nome, cpf, email, telefone, data_nascimento)
        values (%s, 'Jean Macedo', '52998224725', 'jean@exemplo.com',
                '11987654321', '1995-03-10'),
               (%s, 'Maria Souza', '11144477735', 'maria@exemplo.com',
                '21998765432', '1988-11-22')
        """,
        (AUTH_JEAN, AUTH_MARIA),
    )
    yield


@pytest.fixture
def jean(banco):
    return banco.execute(
        "select id from clientes where cpf = '52998224725'"
    ).fetchone()[0]


@pytest.fixture
def maria(banco):
    return banco.execute(
        "select id from clientes where cpf = '11144477735'"
    ).fetchone()[0]


@pytest.fixture
def cabecalho_jean(jean):
    return {"X-Cliente-Id": str(jean)}


@pytest.fixture
def cabecalho_maria(maria):
    return {"X-Cliente-Id": str(maria)}


@pytest.fixture
def abrir_conta(banco):
    def _abrir(cliente_id, tipo="corrente", apelido=None, saldo=None):
        conta_id = banco.execute(
            "select (abrir_conta(%s, %s, %s)).id", (cliente_id, tipo, apelido)
        ).fetchone()[0]
        if saldo is not None:
            banco.execute("select realizar_deposito(%s, %s)", (conta_id, saldo))
        return conta_id

    return _abrir


@pytest.fixture
def conta_do_jean(abrir_conta, jean):
    return abrir_conta(jean, apelido="Dia a dia", saldo="1000.00")


@pytest.fixture
def conta_da_maria(abrir_conta, maria):
    return abrir_conta(maria, apelido="Principal", saldo="500.00")
