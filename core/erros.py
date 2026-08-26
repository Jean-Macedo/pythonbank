"""Erros do domínio.

Todo erro levantado por `core/` é uma subclasse de `ErroDeDominio` e carrega um
`codigo` estável. A camada de apresentação decide o que fazer pelo código, nunca
interpretando a mensagem em português (RF-0.13).

Os códigos são os mesmos de `docs/03-contrato-api.md`.
"""


class ErroDeDominio(Exception):
    """Base de todo erro previsto pelas regras de negócio.

    Representa um estado que o usuário pode alcançar e corrigir: saldo curto,
    CPF errado, limite atingido. Sempre tem `codigo` e mensagem exibível.
    """

    codigo = "ERRO_DE_DOMINIO"
    mensagem_padrao = "Não foi possível completar a operação."

    def __init__(self, mensagem: str | None = None):
        self.mensagem = mensagem or self.mensagem_padrao
        super().__init__(self.mensagem)


class ErroDeProgramacao(Exception):
    """Invariante interna violada — um bug, não uma ação do usuário.

    Deliberadamente **não** é `ErroDeDominio`: nenhuma camada acima deve
    capturá-lo para exibir mensagem. Se aparecer em produção, o conserto é no
    código, não na entrada.
    """


# --------------------------------------------------------------------------
# Movimentação
# --------------------------------------------------------------------------

class ValorInvalido(ErroDeDominio):
    codigo = "VALOR_INVALIDO"
    mensagem_padrao = "O valor precisa ser maior que zero."


class SaldoInsuficiente(ErroDeDominio):
    codigo = "SALDO_INSUFICIENTE"
    mensagem_padrao = "Saldo insuficiente para esta operação."


class ContasIguais(ErroDeDominio):
    codigo = "CONTAS_IGUAIS"
    mensagem_padrao = "Escolha uma conta de destino diferente da de origem."


# --------------------------------------------------------------------------
# Contas
# --------------------------------------------------------------------------

class ContaNaoEncontrada(ErroDeDominio):
    codigo = "CONTA_NAO_ENCONTRADA"
    mensagem_padrao = "Conta não encontrada."


class ContaNaoEncerravel(ErroDeDominio):
    codigo = "CONTA_NAO_ENCERRAVEL"
    mensagem_padrao = "Só é possível encerrar uma conta com saldo zero."


class ContaInativa(ErroDeDominio):
    codigo = "CONTA_NAO_ENCONTRADA"
    mensagem_padrao = "Esta conta está encerrada."


class LimiteDeContas(ErroDeDominio):
    codigo = "LIMITE_DE_CONTAS"
    mensagem_padrao = "Você atingiu o limite de contas abertas."


class ApelidoDuplicado(ErroDeDominio):
    codigo = "APELIDO_DUPLICADO"
    mensagem_padrao = "Você já tem uma conta com este apelido."


class TipoDeContaInvalido(ErroDeDominio):
    codigo = "TIPO_DE_CONTA_INVALIDO"
    mensagem_padrao = "Tipo de conta inválido."


# --------------------------------------------------------------------------
# Cadastro
# --------------------------------------------------------------------------

class NomeInvalido(ErroDeDominio):
    codigo = "NOME_INVALIDO"
    mensagem_padrao = "O nome não pode estar vazio."


class EmailInvalido(ErroDeDominio):
    codigo = "EMAIL_INVALIDO"
    mensagem_padrao = "Informe um e-mail válido."


class TelefoneInvalido(ErroDeDominio):
    codigo = "TELEFONE_INVALIDO"
    mensagem_padrao = "Informe um telefone com DDD, apenas números."


class CpfInvalido(ErroDeDominio):
    codigo = "CPF_INVALIDO"
    mensagem_padrao = "CPF inválido."


class CpfDuplicado(ErroDeDominio):
    codigo = "CPF_DUPLICADO"
    mensagem_padrao = "Já existe um cadastro com este CPF."


class DataNascimentoInvalida(ErroDeDominio):
    """Formato irreconhecível. Distinto de `DataNascimentoFutura` (RN-0.6)."""

    codigo = "DATA_NASCIMENTO_INVALIDA"
    mensagem_padrao = "Formato de data inválido. Use DD/MM/AAAA."


class DataNascimentoFutura(ErroDeDominio):
    codigo = "DATA_NASCIMENTO_FUTURA"
    mensagem_padrao = "A data de nascimento não pode estar no futuro."
