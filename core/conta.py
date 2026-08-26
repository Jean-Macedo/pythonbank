"""Conta bancária — regras de movimentação.

Domínio puro: não importa `supabase`, não importa `fastapi`, não chama `input()`
nem `print()` (DT-05). Na Fase 1 a atomicidade destas operações passa a ser
garantida pelo PostgreSQL; aqui elas guardam as regras que o banco não expressa.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from itertools import count

from core import dinheiro
from core.dinheiro import ZERO
from core.erros import (
    ContaInativa,
    ContaNaoEncerravel,
    ContasIguais,
    SaldoInsuficiente,
    TipoDeContaInvalido,
)
from core.eventos import TipoTransacao, Transacao

AGENCIA_PADRAO = "0001"

# Espelha a sequence `contas_numero_seq` da Fase 1. Enquanto o estado vive em
# memória, a numeração é da aplicação; a partir da F1 quem numera é o banco
# (RN-1.8), porque duas aberturas simultâneas não podem colidir.
_sequencia_numero = count(100001)


def _proximo_numero() -> str:
    return str(next(_sequencia_numero)).zfill(8)


class TipoConta(StrEnum):
    CORRENTE = "corrente"
    POUPANCA = "poupanca"

    @classmethod
    def converter(cls, valor: "str | TipoConta") -> "TipoConta":
        if isinstance(valor, cls):
            return valor
        try:
            return cls(str(valor).strip().lower())
        except ValueError:
            permitidos = ", ".join(t.value for t in cls)
            raise TipoDeContaInvalido(
                f"Tipo de conta inválido. Use um destes: {permitidos}."
            ) from None


class Conta:
    def __init__(
        self,
        cliente,
        tipo: "str | TipoConta",
        apelido: str | None = None,
        agencia: str = AGENCIA_PADRAO,
        numero: str | None = None,
    ):
        self._cliente = cliente
        self._tipo = TipoConta.converter(tipo)
        self._agencia = agencia
        self._numero = numero or _proximo_numero()
        self._apelido = self.normalizar_apelido(apelido)
        self._saldo: Decimal = ZERO
        self._historico: list[Transacao] = []
        self._ativa = True

    # ------------------------------------------------------------------
    # Identidade
    # ------------------------------------------------------------------

    @staticmethod
    def normalizar_apelido(apelido: str | None) -> str | None:
        """Apelido em branco equivale a ausente — evita duas contas 'sem nome'."""
        if apelido is None:
            return None
        limpo = apelido.strip()
        return limpo or None

    @property
    def titular(self):
        return self._cliente

    @property
    def tipo(self) -> TipoConta:
        return self._tipo

    @property
    def agencia(self) -> str:
        return self._agencia

    @property
    def numero(self) -> str:
        return self._numero

    @property
    def identificacao(self) -> str:
        return f"{self._agencia}/{self._numero}"

    @property
    def apelido(self) -> str | None:
        return self._apelido

    @property
    def rotulo(self) -> str:
        """Como a conta se apresenta ao usuário."""
        base = self._apelido or self._tipo.value.capitalize()
        return f"{base} ({self.identificacao})"

    @property
    def ativa(self) -> bool:
        return self._ativa

    @property
    def saldo(self) -> Decimal:
        return self._saldo

    @property
    def historico(self) -> tuple[Transacao, ...]:
        """Cópia imutável: o ledger não é editável de fora (DT-03)."""
        return tuple(self._historico)

    @property
    def saldo_do_ledger(self) -> Decimal:
        """Soma do histórico. Equivale à query de reconciliação (CA-02).

        Deve ser sempre idêntico a `saldo`. É a versão em memória da checagem
        que na Fase 1 roda em SQL.
        """
        return dinheiro.quantizar(
            sum((t.valor_com_sinal for t in self._historico), ZERO)
        )

    # ------------------------------------------------------------------
    # Validações — separadas da mutação para que a API possa chamá-las antes
    # de delegar a escrita ao banco (ver docs/fase-2-api-rest.md)
    # ------------------------------------------------------------------

    def _exigir_ativa(self) -> None:
        if not self._ativa:
            raise ContaInativa()

    def validar_deposito(self, valor) -> Decimal:
        self._exigir_ativa()
        return dinheiro.validar_positivo(valor)

    def validar_saque(self, valor) -> Decimal:
        self._exigir_ativa()
        convertido = dinheiro.validar_positivo(valor)
        if convertido > self._saldo:
            raise SaldoInsuficiente(
                f"Saldo insuficiente. Seu saldo é {dinheiro.formatar(self._saldo)}."
            )
        return convertido

    # ------------------------------------------------------------------
    # Movimentação
    # ------------------------------------------------------------------

    def _registrar(
        self,
        tipo: TipoTransacao,
        valor: Decimal,
        contraparte: str | None = None,
    ) -> Transacao:
        self._saldo = dinheiro.quantizar(self._saldo + valor * tipo.sinal)
        transacao = Transacao(
            tipo=tipo,
            valor=valor,
            saldo_apos=self._saldo,
            data_hora=datetime.now(),
            contraparte=contraparte,
        )
        self._historico.append(transacao)
        return transacao

    def depositar(self, valor) -> Transacao:
        convertido = self.validar_deposito(valor)
        return self._registrar(TipoTransacao.DEPOSITO, convertido)

    def sacar(self, valor) -> Transacao:
        convertido = self.validar_saque(valor)
        return self._registrar(TipoTransacao.SAQUE, convertido)

    def transferir_para(self, destino: "Conta", valor) -> tuple[Transacao, Transacao]:
        """Move valor para outra conta.

        Valida tudo antes de tocar em qualquer saldo: nenhuma das duas contas
        pode ficar alterada se a operação falhar no meio. Na Fase 1 essa garantia
        passa a ser da transação do PostgreSQL (DT-02).
        """
        if destino is self:
            raise ContasIguais()
        self._exigir_ativa()
        destino._exigir_ativa()

        convertido = self.validar_saque(valor)

        saida = self._registrar(
            TipoTransacao.TRANSFERENCIA_SAIDA, convertido, destino.identificacao
        )
        entrada = destino._registrar(
            TipoTransacao.TRANSFERENCIA_ENTRADA, convertido, self.identificacao
        )
        return saida, entrada

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def encerrar(self) -> None:
        """Desativa a conta. Nunca apaga — o ledger precisa continuar íntegro."""
        self._exigir_ativa()
        if self._saldo != ZERO:
            raise ContaNaoEncerravel(
                "Só é possível encerrar uma conta com saldo zero. "
                f"Esta conta tem {dinheiro.formatar(self._saldo)}."
            )
        self._ativa = False

    def renomear(self, apelido: str | None) -> None:
        """Passa pelo cliente, que é quem garante unicidade do apelido."""
        self._cliente.renomear_conta(self, apelido)

    def __repr__(self) -> str:
        estado = "ativa" if self._ativa else "encerrada"
        return f"<Conta {self.identificacao} {self._tipo.value} {estado}>"
