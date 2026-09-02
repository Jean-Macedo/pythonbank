"""Depósito, saque e transferência.

As rotas não calculam saldo: elas validam, delegam à função PL/pgSQL e traduzem
o resultado. A atomicidade é do PostgreSQL (DT-02).
"""

from fastapi import APIRouter, Depends, status

from backend.api.deps import get_conta_do_cliente, get_conta_repo
from backend.api.limite import limitar_movimentacao
from backend.core.erros import ContaNaoEncontrada, ContasIguais
from backend.infra.repositorios import ContaLida, ContaRepo
from backend.schemas import ResultadoTransacao, TransferenciaIn, ValorIn

router = APIRouter(prefix="/api/contas", tags=["movimentação"])


@router.post(
    "/{conta_id}/deposito",
    response_model=ResultadoTransacao,
    status_code=status.HTTP_201_CREATED,
)
def depositar(
    entrada: ValorIn,
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    limitar_movimentacao(conta.cliente_id)

    resultado = repo.depositar(conta.id, entrada.valor)
    return ResultadoTransacao(
        saldo_atual=resultado.saldo, transacao_id=resultado.transacao_id
    )


@router.post(
    "/{conta_id}/saque",
    response_model=ResultadoTransacao,
    status_code=status.HTTP_201_CREATED,
)
def sacar(
    entrada: ValorIn,
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """Saldo insuficiente é decidido pelo `where` do `update`, dentro da função.

    Checar aqui antes de chamar abriria uma janela entre a verificação e a
    escrita — exatamente o defeito que a DT-02 existe para eliminar.
    """
    limitar_movimentacao(conta.cliente_id)

    resultado = repo.sacar(conta.id, entrada.valor)
    return ResultadoTransacao(
        saldo_atual=resultado.saldo, transacao_id=resultado.transacao_id
    )


@router.post(
    "/{conta_id}/transferencia",
    response_model=ResultadoTransacao,
    status_code=status.HTTP_201_CREATED,
)
def transferir(
    entrada: TransferenciaIn,
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """O destino é identificado por agência e número, nunca por id interno.

    O cliente não conhece — nem deveria adivinhar — os ids de contas alheias.
    """
    limitar_movimentacao(conta.cliente_id)

    destino = repo.buscar_por_agencia_numero(
        entrada.agencia_destino, entrada.numero_destino
    )
    if destino is None:
        raise ContaNaoEncontrada("Conta de destino não encontrada.")
    if destino.id == conta.id:
        raise ContasIguais()

    resultado = repo.transferir(conta.id, destino.id, entrada.valor)
    return ResultadoTransacao(
        saldo_atual=resultado.saldo, transacao_id=resultado.transacao_id
    )
