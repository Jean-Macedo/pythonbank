"""Dependências compartilhadas das rotas.

Aqui mora a verificação de titularidade (RN-2.5). Ela existe em **um único
lugar** de propósito: repetida em cada handler, uma rota nova acabaria esquecida,
e é justamente esse o modo de falha mais provável do projeto.
"""

from fastapi import Depends, Header

from backend.config import Configuracao, configuracao
from backend.core.erros import ContaNaoEncontrada, ErroDeDominio
from backend.infra.repositorios import ClienteLido, ClienteRepo, ContaLida, ContaRepo


def get_cliente_repo() -> ClienteRepo:
    return ClienteRepo()


def get_conta_repo() -> ContaRepo:
    return ContaRepo()


class NaoAutenticado(ErroDeDominio):
    codigo = "NAO_AUTENTICADO"
    mensagem_padrao = "Sua sessão expirou. Entre novamente."


def get_cliente_atual(
    x_cliente_id: int | None = Header(default=None, alias="X-Cliente-Id"),
    cfg: Configuracao = Depends(configuracao),
    repo: ClienteRepo = Depends(get_cliente_repo),
) -> ClienteLido:
    """Resolve quem está chamando.

    **Implementação temporária da Fase 2.** Lê o cliente de um cabeçalho, sem
    verificar nada — serve apenas para exercitar o ponto de injeção enquanto a
    autenticação não existe. A Fase 3 substitui o corpo desta função por
    validação de JWT do Supabase Auth, e nada mais no projeto precisa mudar:
    todas as rotas dependem desta assinatura, não da implementação.

    O stub só funciona com `AUTENTICACAO_STUB=true`, e `config.validar_coerencia`
    impede que essa combinação exista em produção.
    """
    if not cfg.autenticacao_stub:
        raise NaoAutenticado(
            "Autenticação ainda não implementada (Fase 3). "
            "Em desenvolvimento, ligue AUTENTICACAO_STUB=true."
        )
    if x_cliente_id is None:
        raise NaoAutenticado()

    cliente = repo.buscar_por_id(x_cliente_id)
    if cliente is None:
        raise NaoAutenticado()
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
