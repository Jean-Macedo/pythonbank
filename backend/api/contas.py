"""Rotas de contas: listar, abrir, detalhar, renomear e encerrar."""

from fastapi import APIRouter, Depends, status

from backend.api.deps import get_cliente_atual, get_conta_do_cliente, get_conta_repo
from backend.core.cliente import Cliente
from backend.core.conta import Conta, TipoConta
from backend.core.erros import ApelidoDuplicado, LimiteDeContas
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

    Limite de contas e unicidade de apelido são *política* e vivem no Python
    (DT-05). O banco impõe a unicidade como rede de segurança, mas a mensagem
    útil vem daqui.
    """
    apelido = Conta.normalizar_apelido(entrada.apelido)

    if repo.contar_ativas(cliente.id) >= Cliente.LIMITE_DE_CONTAS:
        raise LimiteDeContas(
            f"Você já tem {Cliente.LIMITE_DE_CONTAS} contas abertas. "
            "Encerre uma antes de abrir outra."
        )
    if apelido is not None:
        existentes = {a.casefold() for a in repo.apelidos_do_cliente(cliente.id)}
        if apelido.casefold() in existentes:
            raise ApelidoDuplicado()

    tipo = TipoConta.converter(entrada.tipo)
    return para_saida(repo.abrir(cliente.id, tipo.value, apelido))


@router.get("/{conta_id}", response_model=ContaOut)
def detalhar(conta: ContaLida = Depends(get_conta_do_cliente)):
    return para_saida(conta)


@router.patch("/{conta_id}", response_model=ContaOut)
def renomear(
    entrada: RenomearContaIn,
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    apelido = Conta.normalizar_apelido(entrada.apelido)

    if apelido is not None:
        ocupados = {
            a.casefold()
            for a in repo.apelidos_do_cliente(conta.cliente_id)
            if conta.apelido is None or a.casefold() != conta.apelido.casefold()
        }
        if apelido.casefold() in ocupados:
            raise ApelidoDuplicado()

    return para_saida(repo.renomear(conta.id, apelido))


@router.delete("/{conta_id}", status_code=status.HTTP_204_NO_CONTENT)
def encerrar(
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """Desativa a conta. Exige saldo zero — a regra é imposta pelo banco."""
    repo.encerrar(conta.id)
