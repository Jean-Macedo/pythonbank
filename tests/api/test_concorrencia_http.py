"""Concorrência na camada HTTP.

Esta suíte não existia, e é por isso que dois bugs de corrida atravessaram 222
testes verdes: toda a bateria de concorrência do projeto apontava para o SQL, que
estava correto. A camada da API, acrescentada depois, nunca foi exercitada sob
disputa.

Os dois primeiros testes falham na implementação anterior à correção — foi assim
que os defeitos foram confirmados, antes de existir conserto.
"""

import concurrent.futures as cf
from decimal import Decimal

from backend.core.cliente import Cliente

CONCORRENTES = 20


def em_paralelo(tarefa, quantidade):
    with cf.ThreadPoolExecutor(max_workers=quantidade) as executor:
        return list(executor.map(tarefa, range(quantidade)))


class TestComprovanteDaTransacao:
    """O `transacao_id` devolvido tem de ser o do lançamento daquela requisição."""

    def test_ids_devolvidos_sao_todos_distintos(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco
    ):
        """Antes da correção: 20 requisições devolviam 3 ids distintos.

        O id vinha de uma segunda consulta ("último lançamento da conta"), então
        requisições concorrentes recebiam o comprovante umas das outras.
        """

        def depositar(_):
            resposta = cliente_http.post(
                f"/api/contas/{conta_do_jean}/deposito",
                json={"valor": "1.00"},
                headers=cabecalho_jean,
            )
            return resposta.json()["transacao_id"]

        ids = em_paralelo(depositar, CONCORRENTES)
        reais = {
            linha[0]
            for linha in banco.execute(
                "select id from transacoes where conta_id = %s", (conta_do_jean,)
            ).fetchall()
        }

        assert len(set(ids)) == CONCORRENTES, (
            f"{CONCORRENTES} requisições devolveram só {len(set(ids))} ids distintos"
        )
        # subconjunto, não igualdade: a conta já nasce com o depósito da fixture
        assert set(ids) <= reais, "algum id devolvido não corresponde a um lançamento"

    def test_id_devolvido_aponta_para_o_proprio_valor(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco
    ):
        """Não basta ser distinto: tem de ser o lançamento certo."""

        def depositar(i):
            valor = f"{i + 1}.00"
            resposta = cliente_http.post(
                f"/api/contas/{conta_do_jean}/deposito",
                json={"valor": valor},
                headers=cabecalho_jean,
            )
            return resposta.json()["transacao_id"], Decimal(valor)

        for transacao_id, valor in em_paralelo(depositar, CONCORRENTES):
            registrado = banco.execute(
                "select valor from transacoes where id = %s", (transacao_id,)
            ).fetchone()[0]
            assert registrado == valor, (
                f"transacao {transacao_id} devolvida para depósito de {valor}, "
                f"mas registra {registrado}"
            )


class TestLimiteDeContas:
    def test_aberturas_simultaneas_nao_furam_o_limite(
        self, cliente_http, cabecalho_jean, abrir_conta, jean, banco
    ):
        """Antes da correção: limite 5, 10 aberturas simultâneas, 14 contas.

        Contar em Python e inserir depois é check-then-act — todas as
        requisições leem a mesma contagem antes de qualquer uma escrever.
        """
        for i in range(Cliente.LIMITE_DE_CONTAS - 1):
            abrir_conta(jean, apelido=f"Existente {i}")

        def abrir(i):
            return cliente_http.post(
                "/api/contas",
                json={"tipo": "corrente", "apelido": f"Nova {i}"},
                headers=cabecalho_jean,
            ).status_code

        codigos = em_paralelo(abrir, 10)

        assert codigos.count(201) == 1, f"{codigos.count(201)} aberturas venceram"
        assert all(c in (201, 422) for c in codigos)

        ativas = banco.execute(
            "select count(*) from contas where cliente_id = %s and ativa", (jean,)
        ).fetchone()[0]
        assert ativas == Cliente.LIMITE_DE_CONTAS

    def test_apelido_duplicado_sob_concorrencia(
        self, cliente_http, cabecalho_jean, jean, banco
    ):
        """Só uma conta pode ficar com o apelido, mesmo em disputa."""

        def abrir(_):
            return cliente_http.post(
                "/api/contas",
                json={"tipo": "corrente", "apelido": "Reserva"},
                headers=cabecalho_jean,
            ).status_code

        codigos = em_paralelo(abrir, 8)
        assert codigos.count(201) == 1
        assert set(codigos) <= {201, 409}

        com_apelido = banco.execute(
            "select count(*) from contas "
            "where cliente_id = %s and ativa and lower(apelido) = 'reserva'",
            (jean,),
        ).fetchone()[0]
        assert com_apelido == 1


class TestSaquesSimultaneos:
    def test_saldo_nunca_fica_negativo_pela_api(
        self, cliente_http, cabecalho_jean, abrir_conta, jean, banco
    ):
        """Saldo para 10 saques, 20 requisições simultâneas."""
        conta = abrir_conta(jean, apelido="Disputada", saldo="10.00")

        def sacar(_):
            return cliente_http.post(
                f"/api/contas/{conta}/saque",
                json={"valor": "1.00"},
                headers=cabecalho_jean,
            ).status_code

        codigos = em_paralelo(sacar, CONCORRENTES)

        assert codigos.count(201) == 10
        assert codigos.count(422) == CONCORRENTES - 10

        saldo = banco.execute(
            "select saldo from contas where id = %s", (conta,)
        ).fetchone()[0]
        assert saldo == Decimal("0.00")

    def test_reconciliacao_intacta_apos_disputa_via_api(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco
    ):
        """CA-02 continua valendo quando a disputa vem pela API."""

        def movimentar(i):
            rota = "deposito" if i % 2 == 0 else "saque"
            cliente_http.post(
                f"/api/contas/{conta_do_jean}/{rota}",
                json={"valor": "5.00"},
                headers=cabecalho_jean,
            )

        em_paralelo(movimentar, CONCORRENTES)
        divergentes = banco.execute("select * from contas_divergentes").fetchall()
        assert divergentes == []
