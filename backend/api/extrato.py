"""Extrato paginado por cursor (RF-2.8)."""

import base64
import binascii
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from backend.api.deps import get_conta_do_cliente, get_conta_repo
from backend.core.erros import ErroDeDominio
from backend.infra.repositorios import ContaLida, ContaRepo, LancamentoLido
from backend.schemas import ExtratoOut, LancamentoOut

router = APIRouter(prefix="/api/contas", tags=["extrato"])

LIMITE_MAXIMO = 100


class CursorInvalido(ErroDeDominio):
    codigo = "CURSOR_INVALIDO"
    mensagem_padrao = "Paginação inválida. Recarregue o extrato."


def codificar_cursor(lancamento: LancamentoLido) -> str:
    bruto = f"{lancamento.data_hora.isoformat()}|{lancamento.id}"
    return base64.urlsafe_b64encode(bruto.encode()).decode()


def decodificar_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        data_hora, ident = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(data_hora), int(ident)
    except (ValueError, binascii.Error, UnicodeDecodeError) as erro:
        raise CursorInvalido() from erro


@router.get("/{conta_id}/extrato", response_model=ExtratoOut)
def extrato(
    limite: int = Query(default=50, ge=1, le=LIMITE_MAXIMO),
    cursor: str | None = Query(default=None),
    conta: ContaLida = Depends(get_conta_do_cliente),
    repo: ContaRepo = Depends(get_conta_repo),
):
    """Página do histórico, mais recente primeiro.

    Busca `limite + 1` para saber se existe página seguinte sem uma segunda
    consulta de contagem — que ficaria cara conforme o ledger cresce.
    """
    posicao = decodificar_cursor(cursor) if cursor else None
    lancamentos = repo.extrato(conta.id, limite + 1, posicao)

    tem_proxima = len(lancamentos) > limite
    pagina = lancamentos[:limite]

    return ExtratoOut(
        transacoes=[LancamentoOut(**asdict(lanc)) for lanc in pagina],
        proximo_cursor=codificar_cursor(pagina[-1]) if tem_proxima and pagina else None,
    )
