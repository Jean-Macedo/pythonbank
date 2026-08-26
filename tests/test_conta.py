from decimal import Decimal

import pytest

from core.conta import Conta, TipoConta
from core.erros import (
    ContaInativa,
    ContaNaoEncerravel,
    ContasIguais,
    SaldoInsuficiente,
    TipoDeContaInvalido,
    ValorInvalido,
)
from core.eventos import TipoTransacao


class TestAbertura:
    def test_conta_nova_comeca_zerada_e_ativa(self, conta):
        assert conta.saldo == Decimal("0.00")
        assert conta.ativa
        assert conta.historico == ()

    def test_numero_e_unico_entre_contas(self, cliente):
        a = cliente.abrir_conta("corrente")
        b = cliente.abrir_conta("poupanca")
        assert a.numero != b.numero

    def test_tipo_aceita_string_ou_enum(self, cliente):
        assert cliente.abrir_conta("poupanca").tipo is TipoConta.POUPANCA
        assert cliente.abrir_conta(TipoConta.CORRENTE).tipo is TipoConta.CORRENTE

    def test_tipo_invalido_e_erro_de_dominio(self, cliente):
        with pytest.raises(TipoDeContaInvalido):
            cliente.abrir_conta("salario")

    def test_apelido_em_branco_equivale_a_ausente(self, cliente):
        assert cliente.abrir_conta("corrente", "   ").apelido is None


class TestDeposito:
    def test_deposito_soma_ao_saldo(self, conta):
        conta.depositar("100.00")
        assert conta.saldo == Decimal("100.00")

    def test_deposito_registra_no_ledger(self, conta):
        transacao = conta.depositar("100.00")
        assert transacao.tipo is TipoTransacao.DEPOSITO
        assert transacao.valor == Decimal("100.00")
        assert transacao.saldo_apos == Decimal("100.00")
        assert len(conta.historico) == 1

    def test_deposito_zero_e_recusado(self, conta):
        with pytest.raises(ValorInvalido):
            conta.depositar("0")

    def test_deposito_negativo_e_recusado(self, conta):
        with pytest.raises(ValorInvalido):
            conta.depositar("-10.00")

    def test_deposito_recusado_nao_altera_saldo_nem_ledger(self, conta_com_saldo):
        with pytest.raises(ValorInvalido):
            conta_com_saldo.depositar("-10.00")
        assert conta_com_saldo.saldo == Decimal("1000.00")
        assert len(conta_com_saldo.historico) == 1


class TestSaque:
    def test_saque_subtrai_do_saldo(self, conta_com_saldo):
        conta_com_saldo.sacar("250.50")
        assert conta_com_saldo.saldo == Decimal("749.50")

    def test_saque_do_saldo_inteiro_e_permitido(self, conta_com_saldo):
        conta_com_saldo.sacar("1000.00")
        assert conta_com_saldo.saldo == Decimal("0.00")

    def test_saque_acima_do_saldo_e_recusado(self, conta_com_saldo):
        with pytest.raises(SaldoInsuficiente):
            conta_com_saldo.sacar("1000.01")

    def test_saque_recusado_nao_altera_saldo_nem_ledger(self, conta_com_saldo):
        with pytest.raises(SaldoInsuficiente):
            conta_com_saldo.sacar("5000.00")
        assert conta_com_saldo.saldo == Decimal("1000.00")
        assert len(conta_com_saldo.historico) == 1

    def test_saque_zero_e_recusado(self, conta_com_saldo):
        with pytest.raises(ValorInvalido):
            conta_com_saldo.sacar("0")

    def test_saque_em_conta_vazia_e_recusado(self, conta):
        with pytest.raises(SaldoInsuficiente):
            conta.sacar("0.01")


class TestTransferencia:
    def test_transferencia_move_valor_entre_contas(self, cliente):
        origem = cliente.abrir_conta("corrente", "Origem")
        destino = cliente.abrir_conta("poupanca", "Destino")
        origem.depositar("500.00")

        origem.transferir_para(destino, "200.00")

        assert origem.saldo == Decimal("300.00")
        assert destino.saldo == Decimal("200.00")

    def test_transferencia_registra_nas_duas_pontas(self, cliente):
        origem = cliente.abrir_conta("corrente")
        destino = cliente.abrir_conta("poupanca")
        origem.depositar("500.00")

        saida, entrada = origem.transferir_para(destino, "200.00")

        assert saida.tipo is TipoTransacao.TRANSFERENCIA_SAIDA
        assert saida.contraparte == destino.identificacao
        assert entrada.tipo is TipoTransacao.TRANSFERENCIA_ENTRADA
        assert entrada.contraparte == origem.identificacao

    def test_transferencia_para_a_mesma_conta_e_recusada(self, conta_com_saldo):
        with pytest.raises(ContasIguais):
            conta_com_saldo.transferir_para(conta_com_saldo, "10.00")

    def test_transferencia_sem_saldo_nao_altera_nenhuma_das_duas(self, cliente):
        origem = cliente.abrir_conta("corrente")
        destino = cliente.abrir_conta("poupanca")
        origem.depositar("50.00")

        with pytest.raises(SaldoInsuficiente):
            origem.transferir_para(destino, "100.00")

        assert origem.saldo == Decimal("50.00")
        assert destino.saldo == Decimal("0.00")
        assert destino.historico == ()

    def test_transferencia_para_conta_encerrada_e_recusada(self, cliente):
        origem = cliente.abrir_conta("corrente")
        destino = cliente.abrir_conta("poupanca")
        origem.depositar("50.00")
        destino.encerrar()

        with pytest.raises(ContaInativa):
            origem.transferir_para(destino, "10.00")
        assert origem.saldo == Decimal("50.00")


class TestEncerramento:
    def test_encerra_conta_zerada(self, conta):
        conta.encerrar()
        assert not conta.ativa

    def test_nao_encerra_conta_com_saldo(self, conta_com_saldo):
        with pytest.raises(ContaNaoEncerravel):
            conta_com_saldo.encerrar()
        assert conta_com_saldo.ativa

    def test_conta_encerrada_nao_recebe_deposito(self, conta):
        conta.encerrar()
        with pytest.raises(ContaInativa):
            conta.depositar("10.00")

    def test_conta_encerrada_nao_permite_saque(self, conta_com_saldo):
        conta_com_saldo.sacar("1000.00")
        conta_com_saldo.encerrar()
        with pytest.raises(ContaInativa):
            conta_com_saldo.sacar("1.00")

    def test_historico_sobrevive_ao_encerramento(self, conta_com_saldo):
        conta_com_saldo.sacar("1000.00")
        conta_com_saldo.encerrar()
        assert len(conta_com_saldo.historico) == 2


class TestReconciliacao:
    """CA-02 em memória: o saldo nunca pode divergir do ledger (DT-03)."""

    def test_saldo_bate_com_o_ledger_apos_varias_operacoes(self, cliente):
        origem = cliente.abrir_conta("corrente")
        destino = cliente.abrir_conta("poupanca")

        origem.depositar("1000.00")
        origem.sacar("120.35")
        origem.transferir_para(destino, "400.00")
        destino.depositar("0.05")
        destino.sacar("100.00")

        for conta in (origem, destino):
            assert conta.saldo == conta.saldo_do_ledger

    def test_operacoes_recusadas_nao_deixam_rastro(self, conta_com_saldo):
        for valor in ("0", "-1", "999999.00"):
            with pytest.raises((ValorInvalido, SaldoInsuficiente)):
                conta_com_saldo.sacar(valor)
        assert conta_com_saldo.saldo == conta_com_saldo.saldo_do_ledger
        assert len(conta_com_saldo.historico) == 1


class TestLedgerImutavel:
    def test_historico_exposto_e_copia(self, conta_com_saldo):
        historico = conta_com_saldo.historico
        assert isinstance(historico, tuple)
        with pytest.raises(AttributeError):
            historico.append("lançamento forjado")

    def test_transacao_e_congelada(self, conta_com_saldo):
        transacao = conta_com_saldo.historico[0]
        with pytest.raises(Exception):
            transacao.valor = Decimal("999.00")


class TestRegrasDeApresentacaoNaoVazam:
    def test_conta_nao_formata_dinheiro_no_ledger(self, conta_com_saldo):
        """RF-0.11 — o histórico guarda dados, não strings prontas."""
        transacao = conta_com_saldo.historico[0]
        assert isinstance(transacao.valor, Decimal)
        assert not isinstance(transacao.valor, str)


def test_conta_isolada_pode_ser_criada_sem_cliente_completo():
    """O domínio não exige infraestrutura para ser exercitado."""
    conta = Conta(cliente=None, tipo="corrente", numero="00000001")
    conta.depositar("10.00")
    assert conta.saldo == Decimal("10.00")
