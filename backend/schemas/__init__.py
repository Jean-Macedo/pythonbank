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
    estorno_de: int | None = None
    """Aponta para o lançamento que este desfaz."""
    estornado_por: int | None = None
    """Presente quando este já foi desfeito — a tela não oferece estornar de novo."""


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


# ------------------------------------------------------- autenticação (F3)


class RegistroIn(Entrada):
    """Cadastro. Validação de verdade é do domínio — aqui só a forma."""

    nome: str = Field(min_length=1, max_length=120)
    # limites folgados de propósito: quem valida é o domínio, pelos dígitos
    # verificadores. Recusar aqui por comprimento produziria "confira o campo
    # CPF" para um CPF correto digitado com máscara diferente da esperada.
    cpf: str = Field(min_length=11, max_length=20, examples=["529.982.247-25"])
    email: str = Field(max_length=254)
    # sem `pattern`: a normalização e a validação são do domínio, que aceita
    # `(11) 98765-4321` e devolve erro com código próprio se não fechar
    telefone: str = Field(max_length=20, examples=["(11) 98765-4321"])
    data_nascimento: str = Field(examples=["10/03/1995"])
    senha: str = Field(
        min_length=8,
        max_length=72,  # limite do bcrypt: além disso o resto é ignorado em silêncio
        examples=["uma-senha-longa"],
    )


class LoginIn(Entrada):
    email: str
    senha: str


class RefreshIn(Entrada):
    refresh_token: str


class SessaoOut(BaseModel):
    access_token: str
    refresh_token: str
    expira_em: int
    tipo: str = "bearer"


class RegistroOut(BaseModel):
    cliente_id: int
    conta_id: int
    sessao: SessaoOut | None = None
    """Ausente quando a instância exige confirmação de e-mail antes do login."""
