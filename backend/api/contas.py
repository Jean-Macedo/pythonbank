"""Rotas de contas: listar, abrir, detalhar, renomear e encerrar."""

from fastapi import APIRouter, Depends, status

from backend.api.deps import get_cliente_atual, get_conta_do_cliente, get_conta_repo
from backend.core.cliente import Cliente
from backend.core.conta import Conta, TipoConta
from backend.infra.repositorios import ClienteLido, ContaLida, ContaRepo
from backend.schemas import AbrirContaIn, ContaOut, ContasOut, RenomearContaIn

router = APIRouter(prefix="/api/contas", tags=["contas"])


def para_saida(conta: ContaLida) -> ContaOut:
    return ContaOut(
        id=conta.id,
        agencia=conta.agencia,
        numero=conta.numero,
        tipo=conta.tipo,
        apelido=conta.apelido,
        saldo=conta.saldo,
    )


@router.get("", response_model=ContasOut)
def listar(
    cliente: ClienteLido = Depends(get_cliente_atual),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """A rota que a interface carrega primeiro: sem ela o frontend não sabe
    sobre qual conta operar."""
    return ContasOut(contas=[para_saida(c) for c in repo.listar_do_cliente(cliente.id)])


@router.post("", response_model=ContaOut, status_code=status.HTTP_201_CREATED)
def abrir(
    entrada: AbrirContaIn,
    cliente: ClienteLido = Depends(get_cliente_atual),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """Abre conta, aplicando as políticas do domínio antes de tocar no banco.

    O limite continua sendo política do domínio (DT-05) — o número sai de
    `Cliente.LIMITE_DE_CONTAS` — mas quem o **aplica** é o banco, sob lock da
    linha do cliente.

    Contar aqui e inserir depois era check-then-act: medido, 10 aberturas
    simultâneas furaram um limite de 5 e deixaram 14 contas. A unicidade do
    apelido, pelo mesmo motivo, fica com o índice único.
    """
    tipo = TipoConta.converter(entrada.tipo)
    apelido = Conta.normalizar_apelido(entrada.apelido)

    return para_saida(
        repo.abrir(cliente.id, tipo.value, apelido, Cliente.LIMITE_DE_CONTAS)
    )


@router.get("/{conta_id}", response_model=ContaOut)
def detalhar(conta: ContaLida = Depends(get_conta_do_cliente)):
    return para_saida(conta)


@router.patch("/{conta_id}", response_model=ContaOut)
def renomear(
    entrada: RenomearContaIn,
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """Renomeia a conta.

    Sem verificação prévia em Python: o índice `contas_apelido_idx` decide, e o
    repositório traduz a violação em APELIDO_DUPLICADO. Ler os apelidos e
    decidir aqui seria a mesma corrida corrigida na abertura.
    """
    apelido = Conta.normalizar_apelido(entrada.apelido)
    return para_saida(repo.renomear(conta.id, apelido))


@router.delete("/{conta_id}", status_code=status.HTTP_204_NO_CONTENT)
def encerrar(
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """Desativa a conta. Exige saldo zero — a regra é imposta pelo banco."""
    repo.encerrar(conta.id)
