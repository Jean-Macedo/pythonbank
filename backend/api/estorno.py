"""Estorno de um lançamento.

A rota vive sob a conta, e não sob a transação, porque a titularidade é da
conta: `get_conta_do_cliente` já resolve e verifica o dono, e o lançamento é
reconferido contra ela dentro da função PL/pgSQL.
"""

from fastapi import APIRouter, Depends, status

from backend.api.deps import get_conta_do_cliente, get_conta_repo
from backend.core.conta import JANELA_DE_ESTORNO_DIAS
from backend.infra.repositorios import ContaLida, ContaRepo
from backend.schemas import ResultadoTransacao

router = APIRouter(prefix="/api/contas", tags=["estorno"])


@router.post(
    "/{conta_id}/lancamentos/{transacao_id}/estorno",
    response_model=ResultadoTransacao,
    status_code=status.HTTP_201_CREATED,
)
def estornar(
    transacao_id: int,
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """Desfaz um lançamento criando outro, de sinal oposto.

    O original permanece no ledger, intacto (DT-03). O prazo vem do domínio e é
    aplicado pelo banco, dentro da mesma transação — contar os dias em Python e
    escrever depois seria a mesma corrida corrigida no limite de contas.
    """
    resultado = repo.estornar(transacao_id, conta.id, JANELA_DE_ESTORNO_DIAS)
    return ResultadoTransacao(
        saldo_atual=resultado.saldo, transacao_id=resultado.transacao_id
    )
