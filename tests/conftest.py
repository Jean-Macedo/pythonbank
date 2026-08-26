import pytest

from core.cliente import Cliente

# CPFs com dígitos verificadores corretos, usados como dados de teste.
CPF_VALIDO = "52998224725"
CPF_VALIDO_2 = "11144477735"


@pytest.fixture
def cliente():
    return Cliente(
        nome="Jean",
        data_nascimento="10/03/1995",
        cpf=CPF_VALIDO,
        email="jean@exemplo.com",
        telefone="11987654321",
    )


@pytest.fixture
def conta(cliente):
    return cliente.abrir_conta("corrente", "Dia a dia")


@pytest.fixture
def conta_com_saldo(conta):
    conta.depositar("1000.00")
    return conta
