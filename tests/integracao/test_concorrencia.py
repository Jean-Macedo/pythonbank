"""Os testes que justificam a DT-02.

São os únicos que distinguem a implementação correta da errada: uma versão
read-modify-write em Python passa em todos os outros testes do projeto e falha
apenas nestes. Se algum dia alguém "simplificar" as funções PL/pgSQL trazendo a
lógica para a aplicação, é aqui que a suíte quebra.
"""

import concurrent.futures as cf
from decimal import Decimal

import pytest

from tests.integracao.conftest import conectar

CONCORRENTES = 50


def executar_em_paralelo(tarefa, quantidade):
    """Roda `tarefa` em paralelo, cada uma com sua própria conexão.

    Devolve a lista de exceções levantadas — vazia quando todas concluíram.
    """
    with cf.ThreadPoolExecutor(max_workers=quantidade) as executor:
        futuros = [executor.submit(tarefa, i) for i in range(quantidade)]
        erros = []
        for f in cf.as_completed(futuros):
            try:
                f.result()
            except Exception as e:  # noqa: BLE001 - o teste inspeciona o erro
                erros.append(e)
    return erros


class TestDepositosSimultaneos:
    def test_cinquenta_depositos_somam_exatamente(self, banco, abrir, saldo):
        """RNF-1.14 — o teste que falha no modelo read-modify-write.

        Cada thread lendo o saldo, somando em Python e regravando produziria um
        total muito menor que 50: as escritas se sobrescrevem. Com o `update`
        atômico, o resultado é exato.
        """
        conta = abrir()

        def depositar(_):
            with conectar() as con:
                con.execute("select realizar_deposito(%s, 1.00)", (conta,))

        erros = executar_em_paralelo(depositar, CONCORRENTES)
        assert not erros, f"{len(erros)} depósitos falharam: {erros[:3]}"
        assert saldo(conta) == Decimal("50.00")

    def test_cada_deposito_gerou_um_lancamento(self, banco, abrir):
        conta = abrir()

        def depositar(_):
            with conectar() as con:
                con.execute("select realizar_deposito(%s, 1.00)", (conta,))

        executar_em_paralelo(depositar, CONCORRENTES)
        n = banco.execute(
            "select count(*) from transacoes where conta_id = %s", (conta,)
        ).fetchone()[0]
        assert n == CONCORRENTES


class TestSaquesSimultaneos:
    def test_saldo_nunca_fica_negativo_sob_disputa(self, banco, abrir, saldo):
        """Saldo para 10 saques, 50 tentativas simultâneas.

        Exatamente 10 podem vencer. As outras 40 têm de ser recusadas — não
        atendidas com saldo negativo.
        """
        conta = abrir(saldo="10.00")

        def sacar(_):
            with conectar() as con:
                con.execute("select realizar_saque(%s, 1.00)", (conta,))

        erros = executar_em_paralelo(sacar, CONCORRENTES)

        assert saldo(conta) == Decimal("0.00")
        assert len(erros) == CONCORRENTES - 10
        assert all("SALDO_INSUFICIENTE" in str(e) for e in erros)

        efetivados = banco.execute(
            "select count(*) from transacoes where conta_id = %s and tipo = 'saque'",
            (conta,),
        ).fetchone()[0]
        assert efetivados == 10


class TestDeadlock:
    def test_transferencias_cruzadas_nao_travam(self, banco, abrir, saldo):
        """RNF-1.15 — a ordem de lock da RN-1.11 é o que impede o deadlock.

        Sem `order by id for update`, A→B e B→A simultâneas adquirem os locks em
        ordens opostas e o PostgreSQL aborta uma delas com deadlock detected.
        """
        a = abrir(apelido="A", saldo="1000.00")
        b = abrir(tipo="poupanca", apelido="B", saldo="1000.00")

        def transferir(i):
            origem, destino = (a, b) if i % 2 == 0 else (b, a)
            with conectar() as con:
                con.execute("select transferir(%s, %s, 1.00)", (origem, destino))

        erros = executar_em_paralelo(transferir, 40)

        travados = [e for e in erros if "deadlock" in str(e).lower()]
        assert not travados, f"deadlock detectado: {travados[:2]}"
        assert not erros, f"{len(erros)} transferências falharam: {erros[:3]}"

        # 20 em cada sentido, valores iguais: os saldos voltam ao ponto de partida
        assert saldo(a) == Decimal("1000.00")
        assert saldo(b) == Decimal("1000.00")


@pytest.mark.parametrize("rodada", range(3))
def test_reconciliacao_apos_disputa(banco, abrir, saldo, divergentes, rodada):
    """CA-02 sob concorrência: saldo e ledger não podem divergir nem sob disputa."""
    conta = abrir(saldo="100.00")

    def movimentar(i):
        with conectar() as con:
            if i % 2 == 0:
                con.execute("select realizar_deposito(%s, 3.00)", (conta,))
            else:
                con.execute("select realizar_saque(%s, 2.00)", (conta,))

    executar_em_paralelo(movimentar, 30)
    assert divergentes() == []
