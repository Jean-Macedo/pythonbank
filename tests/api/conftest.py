"""Testes da API contra o banco de desenvolvimento e o GoTrue real.

Não uso banco falso nem token forjado: o valor destes testes está justamente em
verificar a tradução entre HTTP, JWT, domínio e PostgreSQL. Um repositório dublê
testaria só o FastAPI conversando consigo mesmo, e um token assinado por nós
testaria a nossa própria suposição sobre o formato, não o do Supabase.

**Por que não vão para o banco separado.** Os testes de integração migraram para
`banco_jean_teste`; estes não podem. Eles precisam de JWT assinado de verdade, e
o GoTrue escreve em `auth.users` do banco principal — o PostgreSQL não faz
foreign key entre bancos, então o cadastro quebraria.

A alternativa é limpar apenas o que a própria sessão criou, e é o que
`base_limpa` faz. Nada de `truncate`: ele apagaria as contas de quem estivesse
com a aplicação aberta.
"""

import contextlib
import random
import uuid

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg não instalado")


def _configuracao_disponivel() -> str | None:
    """Devolve o motivo de não dar para coletar, ou `None` se der.

    Estes testes sobem a aplicação, que exige configuração já no import — o
    `CORSMiddleware` precisa das origens antes de qualquer requisição. Sem
    `.env`, importar os módulos levanta `ValidationError` **na coleta**, e um
    erro de coleta derruba a suíte inteira: quem clonou o repositório e rodou
    `pytest` não veria nem os testes de domínio, que não dependem de nada.

    Descoberto verificando o passo a passo do README num clone limpo.
    """
    try:
        from backend.config import configuracao

        configuracao()
    except Exception as erro:  # noqa: BLE001 - qualquer falha aqui é "sem config"
        return (
            f"configuração ausente ({type(erro).__name__}). "
            "Crie o arquivo: cp .env.example .env"
        )
    return None


_motivo = _configuracao_disponivel()

#: Faz o pytest ignorar este diretório em vez de estourar na coleta.
collect_ignore_glob = ["*.py"] if _motivo else []

import os  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

#: Banco de desenvolvimento — o mesmo que a aplicação usa, de propósito.
DSN = os.environ.get(
    "BANCO_TESTE_DSN", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)


def conectar():
    return psycopg.connect(DSN, autocommit=True, connect_timeout=5)

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
    """Apaga apenas contas e lançamentos **dos titulares desta sessão**.

    Não usa `truncate`. Estes testes rodam no banco de desenvolvimento — não há
    como movê-los — e truncar apagaria as contas de quem estivesse com a
    aplicação aberta. A limpeza é escopada pelos `auth_user_id` criados aqui.

    `session_replication_role = replica` desliga os gatilhos pela duração da
    transação, o que é necessário porque `transacoes_sem_update` recusa `delete`
    — a imutabilidade do ledger, que os testes precisam contornar para limpar o
    que eles mesmos criaram.
    """
    ids = tuple(dado["auth_user_id"] for dado in usuarios.values())
    banco.execute("set session_replication_role = replica")
    try:
        banco.execute(
            """
            delete from transacoes where conta_id in (
                select c.id from contas c
                  join clientes cl on cl.id = c.cliente_id
                 where cl.auth_user_id = any(%s::uuid[])
            )
            """,
            (list(ids),),
        )
        banco.execute(
            """
            delete from contas where cliente_id in (
                select id from clientes where auth_user_id = any(%s::uuid[])
            )
            """,
            (list(ids),),
        )
    finally:
        banco.execute("set session_replication_role = origin")
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


@pytest.fixture(scope="session", autouse=True)
def avisar_sobre_o_banco():
    """Os testes escrevem no mesmo banco usado no desenvolvimento.

    Isso é consequência da DT-06 — um banco local só — e é aceitável, mas não
    é invisível: `contas` e `transacoes` são truncadas a cada teste. Quem
    estiver com a aplicação aberta perde as contas que criou, embora o cadastro
    sobreviva.

    `supabase db reset` devolve o banco ao estado do seed.
    """
    yield
