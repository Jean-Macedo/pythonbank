"""Dependências compartilhadas das rotas.

Aqui moram os dois pontos de controle de acesso:

* `get_cliente_atual` — quem está chamando, provado pelo JWT
* `get_conta_do_cliente` — a conta é dele, verificado em **um único lugar**

O segundo existe uma vez só de propósito: repetido em cada handler, uma rota nova
acabaria esquecida, e é esse o modo de falha mais provável do projeto.
"""

from fastapi import Depends, Header
from jwt import PyJWTError

from backend.core.erros import ContaNaoEncontrada, ErroDeDominio
from backend.infra import autenticacao
from backend.infra.repositorios import ClienteLido, ClienteRepo, ContaLida, ContaRepo


def get_cliente_repo() -> ClienteRepo:
    return ClienteRepo()


def get_conta_repo() -> ContaRepo:
    return ContaRepo()


class NaoAutenticado(ErroDeDominio):
    codigo = "NAO_AUTENTICADO"
    mensagem_padrao = "Sua sessão expirou. Entre novamente."


class CadastroIncompleto(ErroDeDominio):
    codigo = "CADASTRO_INCOMPLETO"
    mensagem_padrao = (
        "Seu usuário existe, mas o cadastro do titular não foi concluído."
    )


def token_do_cabecalho(authorization: str | None) -> str:
    """Extrai o token de `Authorization: Bearer <jwt>`.

    Cabeçalho ausente ou malformado é falha de identificação: 401, e nunca o 422
    do Pydantic — que vazaria a forma interna e fugiria da tabela de erros.
    """
    if not authorization:
        raise NaoAutenticado("Informe o token de acesso.")
    partes = authorization.split(maxsplit=1)
    if len(partes) != 2 or partes[0].lower() != "bearer" or not partes[1].strip():
        raise NaoAutenticado("Formato de autorização inválido. Use: Bearer <token>.")
    return partes[1].strip()


def get_identidade(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> autenticacao.Identidade:
    """Valida o JWT e devolve o que ele afirma. Nada além disso é confiável.

    A validação é local, contra as chaves públicas do JWKS — nenhuma chamada de
    rede no caminho da requisição depois que as chaves estão em cache.
    """
    token = token_do_cabecalho(authorization)
    try:
        return autenticacao.validar_token(token)
    except autenticacao.ServicoIndisponivel:
        raise  # 503, não 401: o token pode estar perfeito
    except PyJWTError as erro:
        # a razão exata (expirado, assinatura inválida, audiência errada) fica no
        # log; para quem chama, toda falha de token é a mesma coisa
        raise NaoAutenticado() from erro


def get_cliente_atual(
    identidade: autenticacao.Identidade = Depends(get_identidade),
    repo: ClienteRepo = Depends(get_cliente_repo),
) -> ClienteLido:
    """Resolve o titular a partir do `sub` do token.

    Token válido sem `clientes` correspondente é um cadastro pela metade — o
    usuário existe no GoTrue mas o registro do titular não foi criado. Responde
    diferente de "não autenticado" porque a ação do usuário também é outra:
    concluir o cadastro, não entrar de novo.
    """
    cliente = repo.buscar_por_auth_id(identidade.auth_user_id)
    if cliente is None:
        raise CadastroIncompleto()
    return cliente


def get_conta_do_cliente(
    conta_id: int,
    cliente: ClienteLido = Depends(get_cliente_atual),
    repo: ContaRepo = Depends(get_conta_repo),
) -> ContaLida:
    """Resolve a conta da URL **e** confirma que ela é do chamador.

    Conta inexistente, conta encerrada e conta de outra pessoa respondem todas
    `CONTA_NAO_ENCONTRADA` → 404. Um 403 confirmaria que o identificador existe
    e permitiria enumerar as contas do banco inteiro (DT-04).
    """
    conta = repo.buscar(conta_id)
    if conta is None or not conta.ativa or conta.cliente_id != cliente.id:
        raise ContaNaoEncontrada()
    return conta
