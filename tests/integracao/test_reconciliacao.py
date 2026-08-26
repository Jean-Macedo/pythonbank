"""Integridade do ledger (CA-02, DT-03).

A view `contas_divergentes` é o teste de integridade do sistema inteiro: enquanto
ela devolver zero linhas, saldo e histórico concordam. Estes testes tentam
quebrá-la de propósito.
"""

import random
from decimal import Decimal

import psycopg
import pytest


class TestReconciliacao:
    def test_operacoes_aleatorias_nao_divergem(self, banco, abrir, divergentes):
        """RNF-1.16 — mil operações, saldo e ledger continuam idênticos."""
        contas = [
            abrir(apelido="A", saldo="10000.00"),
            abrir(tipo="poupanca", apelido="B", saldo="10000.00"),
        ]
        random.seed(42)  # sequência reproduzível: falha aqui é sempre reproduzível

        for _ in range(1000):
            conta = random.choice(contas)
            valor = Decimal(random.randrange(1, 5000)) / 100
            operacao = random.choice(["deposito", "saque", "transferencia"])
            try:
                if operacao == "deposito":
                    banco.execute("select realizar_deposito(%s, %s)", (conta, valor))
                elif operacao == "saque":
                    banco.execute("select realizar_saque(%s, %s)", (conta, valor))
                else:
                    outra = contas[1] if conta == contas[0] else contas[0]
                    banco.execute("select transferir(%s, %s, %s)", (conta, outra, valor))
            except psycopg.errors.RaiseException:
                # saldo insuficiente é resultado legítimo e não pode sujar o ledger
                pass

        assert divergentes() == []

    def test_soma_do_ledger_bate_com_o_saldo(self, banco, abrir):
        conta = abrir(saldo="1000.00")
        banco.execute("select realizar_saque(%s, 250.50)", (conta,))
        banco.execute("select realizar_deposito(%s, 0.05)", (conta,))

        saldo_col, saldo_ledger = banco.execute(
            """
            select c.saldo,
                   coalesce(sum(case when t.tipo in ('deposito','transferencia_entrada')
                                     then t.valor else -t.valor end), 0)
              from contas c left join transacoes t on t.conta_id = c.id
             where c.id = %s group by c.saldo
            """,
            (conta,),
        ).fetchone()
        assert saldo_col == saldo_ledger == Decimal("749.55")

    def test_saldo_apos_reconstroi_a_serie(self, banco, abrir):
        """`saldo_apos` permite montar o extrato sem recalcular a série inteira."""
        conta = abrir()
        for valor in ("100.00", "50.00", "25.00"):
            banco.execute("select realizar_deposito(%s, %s)", (conta, valor))

        série = banco.execute(
            "select saldo_apos from transacoes where conta_id = %s order by id", (conta,)
        ).fetchall()
        assert [s[0] for s in série] == [
            Decimal("100.00"),
            Decimal("150.00"),
            Decimal("175.00"),
        ]


class TestLedgerImutavel:
    """O gatilho `transacoes_sem_update` torna a correção um lançamento novo."""

    def test_update_no_ledger_e_recusado(self, banco, abrir):
        conta = abrir(saldo="100.00")
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("update transacoes set valor = 1 where conta_id = %s", (conta,))
        assert "LEDGER_IMUTAVEL" in str(e.value)

    def test_delete_no_ledger_e_recusado(self, banco, abrir):
        conta = abrir(saldo="100.00")
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("delete from transacoes where conta_id = %s", (conta,))
        assert "LEDGER_IMUTAVEL" in str(e.value)

    def test_recusa_preserva_a_linha(self, banco, abrir):
        conta = abrir(saldo="100.00")
        with pytest.raises(psycopg.errors.RaiseException):
            banco.execute("delete from transacoes where conta_id = %s", (conta,))
        n = banco.execute(
            "select count(*) from transacoes where conta_id = %s", (conta,)
        ).fetchone()[0]
        assert n == 1


class TestPrecisaoDecimal:
    """CA-01 no banco: NUMERIC(15,2) não acumula erro (DT-01)."""

    def test_mil_centavos_somam_exatamente_dez_reais(self, banco, abrir, saldo):
        conta = abrir()
        for _ in range(1000):
            banco.execute("select realizar_deposito(%s, 0.01)", (conta,))
        assert saldo(conta) == Decimal("10.00")

    def test_valor_e_devolvido_como_decimal(self, banco, abrir, saldo):
        conta = abrir(saldo="0.10")
        assert isinstance(saldo(conta), Decimal)

    def test_tres_decimos_nao_viram_dizima(self, banco, abrir, saldo):
        """O caso que motiva a DT-01: 0.1+0.1+0.1 != 0.3 em ponto flutuante."""
        conta = abrir()
        for _ in range(3):
            banco.execute("select realizar_deposito(%s, 0.10)", (conta,))
        assert saldo(conta) == Decimal("0.30")
