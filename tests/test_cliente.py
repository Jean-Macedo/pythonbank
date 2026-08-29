from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.core.cliente import Cliente, cpf_valido
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
from tests.conftest import CPF_VALIDO


def novo_cliente(**sobrescritas):
    dados = {
        "nome": "Jean",
        "data_nascimento": "10/03/1995",
        "cpf": CPF_VALIDO,
        "email": "jean@exemplo.com",
        "telefone": "11987654321",
    }
    dados.update(sobrescritas)
    return Cliente(**dados)


class TestNome:
    def test_aceita_nome_valido(self, cliente):
        assert cliente.nome == "Jean"

    def test_remove_espacos_das_pontas(self):
        assert novo_cliente(nome="  Jean  ").nome == "Jean"

    @pytest.mark.parametrize("invalido", ["", "   ", None, 42])
    def test_rejeita_nome_invalido(self, invalido):
        with pytest.raises(NomeInvalido):
            novo_cliente(nome=invalido)


class TestEmail:
    def test_normaliza_para_minusculas(self):
        assert novo_cliente(email="JEAN@Exemplo.COM").email == "jean@exemplo.com"

    @pytest.mark.parametrize(
        "invalido", ["", "   ", "jean", "jean@", "@exemplo.com", "jean@exemplo", None]
    )
    def test_rejeita_email_invalido(self, invalido):
        with pytest.raises(EmailInvalido):
            novo_cliente(email=invalido)


class TestTelefone:
    @pytest.mark.parametrize("valido", ["1187654321", "11987654321"])
    def test_aceita_dez_e_onze_digitos(self, valido):
        assert novo_cliente(telefone=valido).telefone == valido

    @pytest.mark.parametrize(
        "invalido", ["119876543", "119876543210", "11 98765-4321", "abcdefghijk", None]
    )
    def test_rejeita_telefone_invalido(self, invalido):
        with pytest.raises(TelefoneInvalido):
            novo_cliente(telefone=invalido)


class TestCpf:
    def test_aceita_cpf_formatado(self):
        assert novo_cliente(cpf="529.982.247-25").cpf == CPF_VALIDO

    def test_expoe_versao_formatada(self, cliente):
        assert cliente.cpf_formatado == "529.982.247-25"

    def test_cpf_e_somente_leitura(self, cliente):
        with pytest.raises(AttributeError):
            cliente.cpf = "11144477735"

    @pytest.mark.parametrize(
        "invalido",
        [
            "12345678900",  # onze dígitos, dígito verificador errado
            "11111111111",  # sequência repetida
            "00000000000",
            "5299822472",  # curto demais
            "529982247251",  # longo demais
            "",
            None,
        ],
    )
    def test_rejeita_cpf_invalido(self, invalido):
        with pytest.raises(CpfInvalido):
            novo_cliente(cpf=invalido)

    def test_validador_isolado(self):
        """RN-0.12 — formato correto não basta, os dígitos precisam fechar."""
        assert cpf_valido("52998224725")
        assert cpf_valido("11144477735")
        assert not cpf_valido("52998224724")
        assert not cpf_valido("22222222222")


class TestDataNascimento:
    def test_converte_de_string(self, cliente):
        assert cliente.data_nascimento == date(1995, 3, 10)

    def test_aceita_date_pronto(self):
        assert novo_cliente(data_nascimento=date(1990, 1, 1)).data_nascimento == date(
            1990, 1, 1
        )

    def test_data_futura_tem_erro_proprio(self):
        """RN-0.6 — antes este caso era mascarado como erro de formato."""
        amanha = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")
        with pytest.raises(DataNascimentoFutura):
            novo_cliente(data_nascimento=amanha)

    @pytest.mark.parametrize(
        "invalida", ["1995-03-10", "31/02/1995", "ontem", "", None]
    )
    def test_formato_invalido_tem_erro_proprio(self, invalida):
        with pytest.raises(DataNascimentoInvalida):
            novo_cliente(data_nascimento=invalida)


class TestIdade:
    def test_calcula_idade_em_anos_completos(self):
        """RF-0.1 — esta property levantava TypeError na versão anterior."""
        hoje = date.today()
        nascimento = date(hoje.year - 30, hoje.month, hoje.day)
        assert novo_cliente(data_nascimento=nascimento).idade == 30

    def test_aniversario_ainda_nao_ocorrido_no_ano(self):
        hoje = date.today()
        nascimento = date(hoje.year - 30, 12, 31)
        esperada = 29 if (hoje.month, hoje.day) < (12, 31) else 30
        assert novo_cliente(data_nascimento=nascimento).idade == esperada

    def test_nascido_hoje_tem_zero(self):
        assert novo_cliente(data_nascimento=date.today()).idade == 0


class TestContas:
    def test_cliente_novo_nao_tem_contas(self, cliente):
        assert cliente.contas == ()

    def test_abre_varias_contas(self, cliente):
        cliente.abrir_conta("corrente", "Dia a dia")
        cliente.abrir_conta("poupanca", "Reserva")
        assert len(cliente.contas) == 2

    def test_limite_de_contas_ativas(self, cliente):
        """RN-0.9 — política do domínio, não constraint do banco (DT-05)."""
        for i in range(Cliente.LIMITE_DE_CONTAS):
            cliente.abrir_conta("corrente", f"Conta {i}")
        with pytest.raises(LimiteDeContas):
            cliente.abrir_conta("corrente", "Uma a mais")

    def test_encerrar_libera_vaga_no_limite(self, cliente):
        contas = [
            cliente.abrir_conta("corrente", f"Conta {i}")
            for i in range(Cliente.LIMITE_DE_CONTAS)
        ]
        cliente.encerrar_conta(contas[0])
        cliente.abrir_conta("corrente", "Substituta")
        assert len(cliente.contas) == Cliente.LIMITE_DE_CONTAS

    def test_apelido_duplicado_e_recusado(self, cliente):
        cliente.abrir_conta("corrente", "Reserva")
        with pytest.raises(ApelidoDuplicado):
            cliente.abrir_conta("poupanca", "Reserva")

    def test_apelido_duplicado_ignora_maiusculas(self, cliente):
        cliente.abrir_conta("corrente", "Reserva")
        with pytest.raises(ApelidoDuplicado):
            cliente.abrir_conta("poupanca", "  reserva ")

    def test_varias_contas_sem_apelido_sao_permitidas(self, cliente):
        cliente.abrir_conta("corrente")
        cliente.abrir_conta("poupanca")
        assert len(cliente.contas) == 2

    def test_renomear_conta(self, cliente):
        conta = cliente.abrir_conta("corrente", "Antigo")
        conta.renomear("Novo")
        assert conta.apelido == "Novo"

    def test_renomear_para_apelido_ocupado_e_recusado(self, cliente):
        cliente.abrir_conta("corrente", "Reserva")
        outra = cliente.abrir_conta("poupanca", "Dia a dia")
        with pytest.raises(ApelidoDuplicado):
            outra.renomear("Reserva")

    def test_renomear_mantendo_o_proprio_apelido_e_permitido(self, cliente):
        conta = cliente.abrir_conta("corrente", "Reserva")
        conta.renomear("Reserva")
        assert conta.apelido == "Reserva"

    def test_busca_conta_por_numero(self, cliente):
        conta = cliente.abrir_conta("corrente")
        assert cliente.buscar_conta(conta.numero) is conta

    def test_busca_conta_inexistente(self, cliente):
        with pytest.raises(ContaNaoEncontrada):
            cliente.buscar_conta("99999999")

    def test_conta_encerrada_sai_da_listagem_mas_nao_do_historico(self, cliente):
        conta = cliente.abrir_conta("corrente")
        cliente.encerrar_conta(conta)
        assert conta not in cliente.contas
        assert conta in cliente.todas_as_contas

    def test_encerrar_conta_de_outro_cliente_e_recusado(self, cliente):
        outro = novo_cliente(cpf="11144477735", email="outro@exemplo.com")
        conta_alheia = outro.abrir_conta("corrente")
        with pytest.raises(ContaNaoEncontrada):
            cliente.encerrar_conta(conta_alheia)


class TestPatrimonio:
    def test_soma_saldos_das_contas_ativas(self, cliente):
        a = cliente.abrir_conta("corrente", "A")
        b = cliente.abrir_conta("poupanca", "B")
        a.depositar("100.50")
        b.depositar("200.25")
        assert cliente.patrimonio == Decimal("300.75")

    def test_cliente_sem_contas_tem_patrimonio_zero(self, cliente):
        assert cliente.patrimonio == Decimal("0.00")
