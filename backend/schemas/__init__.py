"""Contrato HTTP (RN-2.3).

Estes modelos descrevem o que entra e sai pela API — não são objetos de domínio.

Dinheiro trafega como **string** no JSON. `JSON.parse` converte número em float
de 64 bits, o que desfaria silenciosamente o cuidado da DT-01 na borda com o
JavaScript.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

#: Valor monetário de entrada: positivo, no máximo duas casas decimais.
ValorEntrada = Annotated[
    Decimal, Field(gt=0, max_digits=15, decimal_places=2, examples=["100.00"])
]

#: Valor monetário de saída: sempre string com duas casas.
ValorSaida = Annotated[
    Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")
]

TipoConta = Literal["corrente", "poupanca"]


class Entrada(BaseModel):
    """Base dos corpos de requisição.

    `extra="ignore"` é deliberado: um `conta_id` enviado no corpo é descartado,
    não obedecido. A conta vem sempre da URL, com titularidade verificada (DT-04).
    """

    model_config = ConfigDict(extra="ignore")


# --------------------------------------------------------------------- saída


class ContaOut(BaseModel):
    id: int
    agencia: str
    numero: str
    tipo: str
    apelido: str | None
    saldo: ValorSaida


class ContasOut(BaseModel):
    contas: list[ContaOut]


class ClienteOut(BaseModel):
    id: int
    nome: str
    cpf: str
    email: str
    telefone: str
    data_nascimento: date


class ResultadoTransacao(BaseModel):
    saldo_atual: ValorSaida
    transacao_id: int


class LancamentoOut(BaseModel):
    id: int
    tipo: str
    valor: ValorSaida
    saldo_apos: ValorSaida
    contraparte: str | None
    data_hora: datetime


class ExtratoOut(BaseModel):
    transacoes: list[LancamentoOut]
    proximo_cursor: str | None


class ErroOut(BaseModel):
    """Formato único de erro. O frontend decide pelo `codigo`, nunca pela
    `mensagem` — que é texto em português, sujeito a mudar."""

    codigo: str
    mensagem: str


# -------------------------------------------------------------------- entrada


class ValorIn(Entrada):
    valor: ValorEntrada


class TransferenciaIn(Entrada):
    valor: ValorEntrada
    agencia_destino: str = Field(pattern=r"^[0-9]{4}$", examples=["0001"])
    numero_destino: str = Field(pattern=r"^[0-9]{1,12}$", examples=["00100002"])


class AbrirContaIn(Entrada):
    tipo: TipoConta
    apelido: str | None = Field(default=None, max_length=60)


class RenomearContaIn(Entrada):
    apelido: str | None = Field(default=None, max_length=60)
