"""Testes da API contra o banco real e o GoTrue real.

Não uso banco falso nem token forjado: o valor destes testes está justamente em
verificar a tradução entre HTTP, JWT, domínio e PostgreSQL. Um repositório dublê
testaria só o FastAPI conversando consigo mesmo, e um token assinado por nós
testaria a nossa própria suposição sobre o formato, não o do Supabase.
"""

import contextlib
import random
import uuid

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg não instalado")

from fastapi.testclient import TestClient  # noqa: E402

from tests.integracao.conftest import DSN, conectar  # noqa: E402

SENHA = "senha-de-teste-bem-longa"


def gerar_cpf(rng: random.Random) -> str:
    """CPF com dígitos verificadores corretos.

    Gerado por sessão, não fixo: `clientes` sobrevive entre execuções (os
    titulares apontam para usuários do GoTrue), então um CPF constante colidiria
    com o da rodada anterior — `cpf` é único no schema.
    """
    base = [rng.randint(0, 9) for _ in range(9)]
    digitos = base[:]
    for tamanho in (9, 10):
        soma = sum(digitos[i] * (tamanho + 1 - i) for i in range(tamanho))
        verificador = (soma * 10) % 11
        digitos.append(0 if verificador == 10 else verificador)
    return "".join(map(str, digitos))


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
    from backend.infra.autenticacao import limpar_cache_jwks

    # cada `supabase db reset` gera chaves de assinatura novas; um cache de outra
    # sessão faria a validação falhar com "kid desconhecido"
    limpar_cache_jwks()

    from backend.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def usuarios(cliente_http):
    """Cria dois titulares de verdade, com token de verdade.

    E-mails únicos por sessão: o GoTrue guarda usuários fora do `truncate`, então
    reaproveitar endereço faria a segunda execução esbarrar em "já cadastrado".
    """
    from backend.infra import autenticacao

    marca = uuid.uuid4().hex[:8]
    rng = random.Random(marca)
    criados = []

    def registrar(nome, cpf, telefone, nascimento):
        email = f"{nome.split()[0].lower()}-{marca}@exemplo-teste.com"
        resposta = cliente_http.post(
            "/auth/registro",
            json={
                "nome": nome,
                "cpf": cpf,
                "email": email,
                "telefone": telefone,
                "data_nascimento": nascimento,
                "senha": SENHA,
            },
        )
        assert resposta.status_code == 201, resposta.text
        corpo = resposta.json()
        with conectar() as con:
            auth_id = con.execute(
                "select auth_user_id from clientes where id = %s", (corpo["cliente_id"],)
            ).fetchone()[0]
        criados.append(auth_id)
        return {
            "email": email,
            "auth_user_id": str(auth_id),
            "token": corpo["sessao"]["access_token"],
        }

    dados = {
        "jean": registrar("Jean Macedo", gerar_cpf(rng), "11987654321", "10/03/1995"),
        "maria": registrar("Maria Souza", gerar_cpf(rng), "21998765432", "22/11/1988"),
    }
    yield dados

    for auth_id in criados:
        with contextlib.suppress(Exception):  # limpeza best-effort
            autenticacao.remover_usuario(auth_id)


@pytest.fixture
def banco():
    with conectar() as con:
        yield con


@pytest.fixture(autouse=True)
def base_limpa(banco, usuarios):
    """Zera contas e lançamentos, preservando os titulares da sessão.

    `clientes` não é truncada: os titulares apontam para usuários do GoTrue, que
    vivem fora do banco. Recriá-los a cada teste exigiria recriar os usuários
    também — e os tokens junto.
    """
    banco.execute("truncate transacoes, contas restart identity cascade")
    yield


def _cliente_id(banco, auth_user_id):
    return banco.execute(
        "select id from clientes where auth_user_id = %s", (auth_user_id,)
    ).fetchone()[0]


@pytest.fixture
def jean(banco, usuarios):
    return _cliente_id(banco, usuarios["jean"]["auth_user_id"])


@pytest.fixture
def maria(banco, usuarios):
    return _cliente_id(banco, usuarios["maria"]["auth_user_id"])


@pytest.fixture
def cabecalho_jean(usuarios):
    return {"Authorization": f"Bearer {usuarios['jean']['token']}"}


@pytest.fixture
def cabecalho_maria(usuarios):
    return {"Authorization": f"Bearer {usuarios['maria']['token']}"}


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
