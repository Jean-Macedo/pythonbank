"""Cliente — dados cadastrais e as contas que ele possui.

Um cliente agrega N contas (RF-0.8). As regras de quantas contas pode ter e de
como elas se distinguem são *política*, e por isso vivem aqui e não no banco
(DT-05).
"""

import re
from datetime import date, datetime

from backend.core.conta import Conta, TipoConta
from backend.core.erros import (
    ApelidoDuplicado,
    ContaNaoEncontrada,
    CpfInvalido,
    DataNascimentoFutura,
    DataNascimentoInvalida,
    EmailInvalido,
    LimiteDeContas,
    NomeInvalido,
    TelefoneInvalido,
)

FORMATO_DATA = "%d/%m/%Y"
PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def cpf_valido(cpf: str) -> bool:
    """Valida os dois dígitos verificadores (RN-0.12).

    Formato correto não é o bastante: `12345678900` tem onze dígitos e é
    inválido. Sequências repetidas passam no cálculo e são rejeitadas à parte.
    """
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    if cpf == cpf[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False
    return True


class Cliente:
    LIMITE_DE_CONTAS = 5
    """Máximo de contas ativas simultâneas (RN-0.9)."""

    def __init__(self, nome, data_nascimento, cpf, email, telefone):
        self.nome = nome
        self.data_nascimento = data_nascimento
        self._cpf = self._validar_cpf(cpf)
        self.email = email
        self.telefone = telefone
        self._contas: list[Conta] = []

    # ------------------------------------------------------------------
    # Dados cadastrais
    # ------------------------------------------------------------------

    @property
    def nome(self) -> str:
        return self._nome

    @nome.setter
    def nome(self, novo_nome):
        if not isinstance(novo_nome, str) or not novo_nome.strip():
            raise NomeInvalido()
        self._nome = novo_nome.strip()

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, novo_email):
        if not isinstance(novo_email, str) or not PADRAO_EMAIL.match(novo_email.strip()):
            raise EmailInvalido()
        self._email = novo_email.strip().lower()

    @property
    def telefone(self) -> str:
        return self._telefone

    @telefone.setter
    def telefone(self, numero):
        if not isinstance(numero, str) or not numero.isdigit():
            raise TelefoneInvalido("Digite apenas números, com DDD.")
        if len(numero) not in (10, 11):
            raise TelefoneInvalido()
        self._telefone = numero

    @property
    def data_nascimento(self) -> date:
        return self._data_nascimento

    @data_nascimento.setter
    def data_nascimento(self, valor):
        """Converte de `DD/MM/AAAA` ou aceita um `date` pronto.

        Data futura e formato irreconhecível são erros distintos (RN-0.6): antes,
        o `except ValueError` capturava o próprio `raise` da checagem de futuro e
        devolvia 'formato inválido', escondendo o motivo real.
        """
        if isinstance(valor, datetime):
            valor = valor.date()

        if isinstance(valor, date):
            convertida = valor
        else:
            try:
                convertida = datetime.strptime(valor, FORMATO_DATA).date()
            except (ValueError, TypeError):
                raise DataNascimentoInvalida() from None

        # fora do try: este erro não pode ser confundido com erro de formato
        if convertida > date.today():
            raise DataNascimentoFutura()

        self._data_nascimento = convertida

    @property
    def cpf(self) -> str:
        return self._cpf

    @staticmethod
    def _validar_cpf(cpf) -> str:
        somente_digitos = re.sub(r"\D", "", cpf or "")
        if not cpf_valido(somente_digitos):
            raise CpfInvalido()
        return somente_digitos

    @property
    def cpf_formatado(self) -> str:
        c = self._cpf
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"

    @property
    def idade(self) -> int:
        """Idade em anos completos.

        O parêntese em torno da comparação é o que a versão anterior não tinha:
        sem ele a expressão era `(int - int - tupla) < tupla` e levantava
        `TypeError` (RF-0.1).
        """
        hoje = date.today()
        nasc = self._data_nascimento
        return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))

    # ------------------------------------------------------------------
    # Contas
    # ------------------------------------------------------------------

    @property
    def contas(self) -> tuple[Conta, ...]:
        """Contas ativas, na ordem de abertura."""
        return tuple(c for c in self._contas if c.ativa)

    @property
    def todas_as_contas(self) -> tuple[Conta, ...]:
        """Inclui as encerradas — o histórico delas continua existindo."""
        return tuple(self._contas)

    def abrir_conta(self, tipo: "str | TipoConta", apelido: str | None = None) -> Conta:
        if len(self.contas) >= self.LIMITE_DE_CONTAS:
            raise LimiteDeContas(
                f"Você já tem {self.LIMITE_DE_CONTAS} contas abertas. "
                "Encerre uma antes de abrir outra."
            )
        apelido = Conta.normalizar_apelido(apelido)
        self._exigir_apelido_livre(apelido)

        conta = Conta(cliente=self, tipo=tipo, apelido=apelido)
        self._contas.append(conta)
        return conta

    def buscar_conta(self, numero: str) -> Conta:
        for conta in self.contas:
            if conta.numero == numero or conta.identificacao == numero:
                return conta
        raise ContaNaoEncontrada()

    def renomear_conta(self, conta: Conta, apelido: str | None) -> None:
        if conta not in self._contas:
            raise ContaNaoEncontrada()
        apelido = Conta.normalizar_apelido(apelido)
        self._exigir_apelido_livre(apelido, exceto=conta)
        conta._apelido = apelido

    def encerrar_conta(self, conta: Conta) -> None:
        if conta not in self._contas:
            raise ContaNaoEncontrada()
        conta.encerrar()

    def _exigir_apelido_livre(self, apelido: str | None, exceto: Conta | None = None):
        """Apelido é único dentro do cliente, ignorando maiúsculas (RN-0.9).

        Espelha o índice `contas_apelido_idx` da Fase 1, que usa `lower(apelido)`.
        """
        if apelido is None:
            return
        alvo = apelido.casefold()
        for conta in self.contas:
            if conta is exceto or conta.apelido is None:
                continue
            if conta.apelido.casefold() == alvo:
                raise ApelidoDuplicado()

    @property
    def patrimonio(self):
        """Soma dos saldos das contas ativas."""
        from backend.core.dinheiro import ZERO, quantizar

        return quantizar(sum((c.saldo for c in self.contas), ZERO))

    def __repr__(self) -> str:
        return f"<Cliente {self._nome} ({len(self.contas)} contas)>"
