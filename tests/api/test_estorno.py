"""Estorno: o lançamento novo desfaz o efeito, sem tocar no original.

É a prova prática da DT-03 — "correção é lançamento de sinal oposto, nunca um
`update` ou `delete` no histórico". A frase estava no documento desde a Fase 1;
aqui ela vira comportamento verificável.
"""

import concurrent.futures as cf
from decimal import Decimal

import pytest


def estornar(cliente_http, cabecalho, conta_id, transacao_id):
    return cliente_http.post(
        f"/api/contas/{conta_id}/lancamentos/{transacao_id}/estorno",
        headers=cabecalho,
    )


def depositar(cliente_http, cabecalho, conta_id, valor):
    return cliente_http.post(
        f"/api/contas/{conta_id}/deposito", json={"valor": valor}, headers=cabecalho
    ).json()["transacao_id"]


class TestOOriginalPermaneceIntacto:
    def test_o_lancamento_estornado_continua_no_ledger(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco
    ):
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "200.00")
        estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)

        original = banco.execute(
            "select tipo, valor from transacoes where id = %s", (lancamento,)
        ).fetchone()
        assert original == ("deposito", Decimal("200.00"))

    def test_os_dois_aparecem_no_extrato_e_se_apontam(
        self, cliente_http, cabecalho_jean, conta_do_jean
    ):
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "200.00")
        estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)

        extrato = cliente_http.get(
            f"/api/contas/{conta_do_jean}/extrato", headers=cabecalho_jean
        ).json()["transacoes"]

        estorno = next(t for t in extrato if t["tipo"] == "estorno_saida")
        assert estorno["estorno_de"] == lancamento

        original = next(t for t in extrato if t["id"] == lancamento)
        assert original["estornado_por"] == estorno["id"]

    def test_o_ledger_ganha_linha_em_vez_de_perder(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco
    ):
        def total():
            return banco.execute(
                "select count(*) from transacoes where conta_id = %s", (conta_do_jean,)
            ).fetchone()[0]

        antes = total()
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "50.00")
        estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)
        assert total() == antes + 2  # o depósito e o estorno dele


class TestPorTipoDeLancamento:
    def test_deposito_devolve_o_dinheiro(
        self, cliente_http, cabecalho_jean, conta_do_jean
    ):
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "200.00")
        resposta = estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)

        assert resposta.status_code == 201
        assert resposta.json()["saldo_atual"] == "1000.00"

    def test_saque_devolve_o_dinheiro(
        self, cliente_http, cabecalho_jean, conta_do_jean
    ):
        saque = cliente_http.post(
            f"/api/contas/{conta_do_jean}/saque",
            json={"valor": "300.00"},
            headers=cabecalho_jean,
        ).json()["transacao_id"]

        resposta = estornar(cliente_http, cabecalho_jean, conta_do_jean, saque)
        assert resposta.json()["saldo_atual"] == "1000.00"

    def test_transferencia_desfaz_as_duas_pernas(
        self, cliente_http, cabecalho_jean, conta_do_jean, abrir_conta, jean, banco
    ):
        destino = abrir_conta(jean, tipo="poupanca", apelido="Destino")
        agencia, numero = banco.execute(
            "select agencia, numero from contas where id = %s", (destino,)
        ).fetchone()

        transferencia = cliente_http.post(
            f"/api/contas/{conta_do_jean}/transferencia",
            json={
                "valor": "150.00",
                "agencia_destino": agencia,
                "numero_destino": numero,
            },
            headers=cabecalho_jean,
        ).json()["transacao_id"]

        resposta = estornar(cliente_http, cabecalho_jean, conta_do_jean, transferencia)

        assert resposta.status_code == 201
        assert resposta.json()["saldo_atual"] == "1000.00"

        saldo_destino = banco.execute(
            "select saldo from contas where id = %s", (destino,)
        ).fetchone()[0]
        assert saldo_destino == Decimal("0.00")


class TestOQueNaoPodeSerEstornado:
    def test_quem_recebeu_nao_desfaz_o_que_o_outro_mandou(
        self,
        cliente_http,
        cabecalho_jean,
        cabecalho_maria,
        conta_do_jean,
        conta_da_maria,
        banco,
    ):
        """Permitir isso deixaria alguém puxar de volta dinheiro alheio."""
        agencia, numero = banco.execute(
            "select agencia, numero from contas where id = %s", (conta_da_maria,)
        ).fetchone()
        cliente_http.post(
            f"/api/contas/{conta_do_jean}/transferencia",
            json={
                "valor": "100.00",
                "agencia_destino": agencia,
                "numero_destino": numero,
            },
            headers=cabecalho_jean,
        )
        entrada = banco.execute(
            "select id from transacoes where conta_id = %s "
            "and tipo = 'transferencia_entrada'",
            (conta_da_maria,),
        ).fetchone()[0]

        resposta = estornar(cliente_http, cabecalho_maria, conta_da_maria, entrada)
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "ESTORNO_NAO_PERMITIDO"

    def test_estorno_de_estorno(self, cliente_http, cabecalho_jean, conta_do_jean):
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "100.00")
        estorno = estornar(
            cliente_http, cabecalho_jean, conta_do_jean, lancamento
        ).json()["transacao_id"]

        resposta = estornar(cliente_http, cabecalho_jean, conta_do_jean, estorno)
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "ESTORNO_DE_ESTORNO"

    def test_duas_vezes_o_mesmo(self, cliente_http, cabecalho_jean, conta_do_jean):
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "100.00")
        estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)

        resposta = estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)
        assert resposta.status_code == 409
        assert resposta.json()["codigo"] == "JA_ESTORNADO"

    def test_deposito_ja_gasto(self, cliente_http, cabecalho_jean, conta_do_jean):
        """Sem saldo para devolver, é recusado — o estorno não deixa negativo."""
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "100.00")
        cliente_http.post(
            f"/api/contas/{conta_do_jean}/saque",
            json={"valor": "1100.00"},
            headers=cabecalho_jean,
        )

        resposta = estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "SALDO_INSUFICIENTE"

    def test_lancamento_inexistente(self, cliente_http, cabecalho_jean, conta_do_jean):
        assert estornar(
            cliente_http, cabecalho_jean, conta_do_jean, 999999
        ).status_code == 404


class TestTitularidade:
    def test_lancamento_de_outra_conta(
        self, cliente_http, cabecalho_jean, cabecalho_maria, conta_do_jean,
        conta_da_maria,
    ):
        """Saber o id de um lançamento alheio não basta para estorná-lo."""
        alheio = depositar(cliente_http, cabecalho_maria, conta_da_maria, "50.00")

        resposta = estornar(cliente_http, cabecalho_jean, conta_do_jean, alheio)
        assert resposta.status_code == 404

    def test_conta_alheia_na_url(
        self, cliente_http, cabecalho_jean, cabecalho_maria, conta_da_maria
    ):
        alheio = depositar(cliente_http, cabecalho_maria, conta_da_maria, "50.00")

        resposta = estornar(cliente_http, cabecalho_jean, conta_da_maria, alheio)
        assert resposta.status_code == 404
        assert resposta.json()["codigo"] == "CONTA_NAO_ENCONTRADA"


class TestConcorrencia:
    def test_estornos_simultaneos_do_mesmo_lancamento(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco
    ):
        """Só um pode vencer, senão o dinheiro sai em dobro.

        É a mesma corrida do limite de contas: sem o lock e o índice único,
        todos passariam pela verificação de "ainda não estornado" antes de
        qualquer um escrever.
        """
        lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, "200.00")

        def tentar(_):
            return estornar(
                cliente_http, cabecalho_jean, conta_do_jean, lancamento
            ).status_code

        with cf.ThreadPoolExecutor(max_workers=10) as executor:
            codigos = list(executor.map(tentar, range(10)))

        assert codigos.count(201) == 1, f"{codigos.count(201)} estornos venceram"
        saldo = banco.execute(
            "select saldo from contas where id = %s", (conta_do_jean,)
        ).fetchone()[0]
        assert saldo == Decimal("1000.00")


class TestReconciliacao:
    @pytest.mark.parametrize("rodada", range(2))
    def test_estorno_nao_faz_saldo_divergir(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco, rodada
    ):
        """CA-02 com os tipos novos.

        Se a view não somasse `estorno_entrada` e `estorno_saida`, toda conta
        com estorno passaria a aparecer como divergente — e o critério de aceite
        mais importante do projeto falharia por engano.
        """
        for valor in ("10.00", "20.00", "30.00"):
            lancamento = depositar(cliente_http, cabecalho_jean, conta_do_jean, valor)
            estornar(cliente_http, cabecalho_jean, conta_do_jean, lancamento)

        assert banco.execute("select * from contas_divergentes").fetchall() == []
