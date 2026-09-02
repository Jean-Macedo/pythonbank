"""Integração com o Supabase Auth (GoTrue).

Duas responsabilidades separadas de propósito:

* **Validar** o token que chega — feito localmente, sem rede, contra as chaves
  públicas do JWKS. Uma requisição autenticada não pode depender de um salto de
  rede extra.
* **Emitir** tokens (cadastro, login, renovação) — delegado ao GoTrue por HTTP.
  O backend nunca vê nem armazena senha.

O token do Supabase é assinado com **ES256**, chave assimétrica. O `JWT_SECRET`
que aparece no `supabase status` não valida nada disso: é resquício do esquema
simétrico antigo. Validar com ele falha em toda requisição, e é um erro fácil de
cometer porque o segredo está bem visível na saída do CLI.
"""

from dataclasses import dataclass

import httpx
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from backend.config import configuracao

# Só assimétricos. O JWKS serve exclusivamente chaves públicas; aceitar HS256
# junto é o setup clássico de confusão de algoritmo — o PyJWT bloqueia usar uma
# chave EC como segredo HMAC, mas a lista não precisa carregar esse risco.
ALGORITMOS = ["ES256", "RS256"]
AUDIENCIA = "authenticated"

_jwks: PyJWKClient | None = None


class ServicoIndisponivel(Exception):
    """O serviço de autenticação não respondeu.

    Distinto de token inválido: o token de quem chamou pode estar perfeito. Virar
    401 mandaria a pessoa fazer login — que também não vai funcionar — e
    esconderia uma indisponibilidade atrás de um erro de credencial.
    """


class ErroDeAutenticacao(Exception):
    """Falha ao emitir credencial. Distinta de token inválido na entrada."""

    codigo_gotrue: str | None = None

    def __init__(self, mensagem: str, status: int = 400):
        self.mensagem = mensagem
        self.status = status
        super().__init__(mensagem)


@dataclass(frozen=True, slots=True)
class Identidade:
    """O que o token afirma. Nada além disto é confiável."""

    auth_user_id: str
    email: str | None


@dataclass(frozen=True, slots=True)
class Credencial:
    access_token: str
    refresh_token: str
    expira_em: int


def jwks() -> PyJWKClient:
    """Cliente JWKS, com cache das chaves entre requisições.

    `PyJWKClient` guarda as chaves em cache e só refaz a busca quando aparece um
    `kid` desconhecido — que é exatamente o comportamento desejado quando o
    Supabase rotaciona a chave de assinatura.
    """
    global _jwks
    if _jwks is None:
        cfg = configuracao()
        _jwks = PyJWKClient(
            f"{cfg.supabase_url}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
            lifespan=600,
        )
    return _jwks


def limpar_cache_jwks() -> None:
    """Usado pelos testes; o Supabase local gera chaves novas a cada reset."""
    global _jwks
    _jwks = None


def validar_token(token: str) -> Identidade:
    """Valida assinatura, expiração e audiência. Levanta `jwt.PyJWTError` se falhar.

    A verificação é local: nenhuma chamada de rede no caminho de uma requisição
    autenticada, contanto que o JWKS já esteja em cache.
    """
    try:
        chave = jwks().get_signing_key_from_jwt(token)
    except PyJWKClientConnectionError as erro:
        raise ServicoIndisponivel(str(erro)) from erro

    conteudo = jwt.decode(
        token,
        chave.key,
        algorithms=ALGORITMOS,
        audience=AUDIENCIA,
        issuer=configuracao().emissor_esperado,
        options={"require": ["exp", "sub", "iss"]},
    )
    return Identidade(auth_user_id=conteudo["sub"], email=conteudo.get("email"))


# ---------------------------------------------------------------------------
# Emissão de credenciais — delegada ao GoTrue
# ---------------------------------------------------------------------------


def _cliente_http() -> httpx.Client:
    cfg = configuracao()
    return httpx.Client(
        base_url=f"{cfg.supabase_url}/auth/v1",
        headers={"apikey": cfg.supabase_anon_key},
        timeout=10.0,
    )


def _credencial(dados: dict) -> Credencial:
    return Credencial(
        access_token=dados["access_token"],
        refresh_token=dados["refresh_token"],
        expira_em=dados.get("expires_in", 3600),
    )


def _erro_do_gotrue(resposta: httpx.Response) -> ErroDeAutenticacao:
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {}
    mensagem = corpo.get("msg") or corpo.get("error_description") or corpo.get("message")
    erro = ErroDeAutenticacao(
        mensagem or "Não foi possível autenticar.", resposta.status_code
    )
    # `error_code` é campo estruturado do GoTrue; a mensagem é texto em inglês
    # que muda entre versões e não serve para decidir nada
    erro.codigo_gotrue = corpo.get("error_code") or corpo.get("code")
    return erro


def criar_usuario(email: str, senha: str) -> tuple[str, Credencial | None]:
    """Cria o usuário no GoTrue e devolve `(auth_user_id, credencial)`.

    A credencial vem `None` quando a instância exige confirmação de e-mail: o
    usuário existe, mas ainda não pode entrar.
    """
    with _cliente_http() as http:
        resposta = http.post("/signup", json={"email": email, "password": senha})

    if resposta.status_code >= 400:
        raise _erro_do_gotrue(resposta)

    dados = resposta.json()
    usuario = dados.get("user") or dados
    auth_user_id = usuario.get("id")
    if not auth_user_id:
        raise ErroDeAutenticacao("Resposta inesperada do serviço de autenticação.", 502)

    credencial = _credencial(dados) if dados.get("access_token") else None
    return auth_user_id, credencial


def autenticar(email: str, senha: str) -> Credencial:
    with _cliente_http() as http:
        resposta = http.post(
            "/token", params={"grant_type": "password"},
            json={"email": email, "password": senha},
        )
    if resposta.status_code >= 400:
        # não distinguir "e-mail não existe" de "senha errada": a diferença
        # permitiria descobrir quais e-mails têm conta no banco
        raise ErroDeAutenticacao("E-mail ou senha incorretos.", 401)
    return _credencial(resposta.json())


def renovar(refresh_token: str) -> Credencial:
    with _cliente_http() as http:
        resposta = http.post(
            "/token", params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
        )
    if resposta.status_code >= 400:
        raise ErroDeAutenticacao("Sessão expirada. Entre novamente.", 401)
    return _credencial(resposta.json())


def remover_usuario(auth_user_id: str) -> None:
    """Desfaz `criar_usuario`. Usado quando o cadastro falha depois do GoTrue.

    Exige a chave de serviço — é operação administrativa.
    """
    cfg = configuracao()
    with httpx.Client(
        base_url=f"{cfg.supabase_url}/auth/v1",
        headers={
            "apikey": cfg.supabase_service_role_key,
            "Authorization": f"Bearer {cfg.supabase_service_role_key}",
        },
        timeout=10.0,
    ) as http:
        resposta = http.delete(f"/admin/users/{auth_user_id}")

    # esta é a compensação que impede usuário órfão; falhar calado aqui é o
    # oposto do que ela existe para fazer
    if resposta.status_code >= 400:
        raise ErroDeAutenticacao(
            f"Não foi possível remover o usuário {auth_user_id}: "
            f"{resposta.status_code}",
            502,
        )
