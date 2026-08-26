"""Eventos do ledger (RF-0.11).

A conta deixa de guardar histórico como lista de strings formatadas e passa a
registrar eventos estruturados. Formatação é responsabilidade da apresentação —
o domínio não sabe se o destino é um terminal, um JSON ou um PDF.

Os valores de `TipoTransacao` são os mesmos da constraint `check` da tabela
`transacoes` em `docs/02-modelo-de-dados.md`.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from core.erros import ErroDeProgramacao


class TipoTransacao(StrEnum):
    DEPOSITO = "deposito"
    SAQUE = "saque"
    TRANSFERENCIA_SAIDA = "transferencia_saida"
    TRANSFERENCIA_ENTRADA = "transferencia_entrada"

    @property
    def e_entrada(self) -> bool:
        return self in (TipoTransacao.DEPOSITO, TipoTransacao.TRANSFERENCIA_ENTRADA)

    @property
    def sinal(self) -> int:
        return 1 if self.e_entrada else -1


@dataclass(frozen=True, slots=True)
class Transacao:
    """Um lançamento no ledger. Imutável: correção é lançamento novo (DT-03)."""

    tipo: TipoTransacao
    valor: Decimal
    saldo_apos: Decimal
    data_hora: datetime
    contraparte: str | None = None
    """Número da conta da outra ponta, presente apenas em transferências."""

    def __post_init__(self) -> None:
        tem_contraparte = self.contraparte is not None
        e_transferencia = self.tipo in (
            TipoTransacao.TRANSFERENCIA_SAIDA,
            TipoTransacao.TRANSFERENCIA_ENTRADA,
        )
        if tem_contraparte != e_transferencia:
            # espelha a constraint `contraparte_coerente` da Fase 1; nenhuma
            # entrada de usuário produz isso, só código errado
            raise ErroDeProgramacao(
                "contraparte deve existir se e somente se for transferência"
            )

    @property
    def valor_com_sinal(self) -> Decimal:
        return self.valor * self.tipo.sinal
