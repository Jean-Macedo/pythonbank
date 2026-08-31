"""Row Level Security: a barreira do acesso **direto** ao banco (RN-3.5 a 3.7).

Estes testes não passam pela nossa API. Eles batem no PostgREST, na porta 54321,
que é uma superfície exposta e independente do backend — qualquer um de posse da
chave anônima chega lá.

ATÉ ONDE ISTO PROTEGE. O backend conecta como dono do banco, e dono ignora RLS.
Portanto a RLS **não** é rede contra bug de roteamento na API; quem cobre isso é
`get_conta_do_cliente`, com um teste por rota em `test_titularidade.py`. Confundir
as duas coisas levaria a confiar numa proteção que não existe naquele caminho.
"""

import httpx
import pytest

from backend.config import configuracao

REST = f"{configuracao().supabase_url}/rest/v1"
ANON = configuracao().supabase_anon_key


def como(token: str | None = None) -> httpx.Client:
    """Cliente HTTP falando com o PostgREST, opcionalmente autenticado."""
    cabecalhos = {"apikey": ANON}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=REST, headers=cabecalhos, timeout=10.0)


@pytest.fixture
def token_jean(usuarios):
    return usuarios["jean"]["token"]


@pytest.fixture
def token_maria(usuarios):
    return usuarios["maria"]["token"]


class TestLeituraAnonima:
    """RN-3.7 — quem não se identificou não lê nada."""

    @pytest.mark.parametrize("tabela", ["clientes", "contas", "transacoes"])
    def test_anonimo_nao_le_tabela_nenhuma(self, tabela, conta_do_jean):
        with como() as http:
            resposta = http.get(f"/{tabela}", params={"select": "*"})
        assert resposta.status_code in (200, 401, 403)
        if resposta.status_code == 200:
            assert resposta.json() == [], f"{tabela} vazou para anônimo"


class TestIsolamentoEntreTitulares:
    """RNF-3.11 — consulta direta com o token de A não traz linha de B.

    Este é o teste que detecta RLS mal configurada. A aplicação continuaria
    funcionando normalmente com as policies erradas, porque a camada Python
    filtra certo; só uma consulta feita **por fora** revela o problema.
    """

    def test_contas_so_traz_as_proprias(
        self, token_jean, conta_do_jean, conta_da_maria
    ):
        with como(token_jean) as http:
            resposta = http.get("/contas", params={"select": "id,cliente_id"})
        assert resposta.status_code == 200

        ids = [linha["id"] for linha in resposta.json()]
        assert conta_do_jean in ids
        assert conta_da_maria not in ids, "conta da Maria vazou para o token do Jean"

    def test_filtro_explicito_pela_conta_alheia_volta_vazio(
        self, token_jean, conta_da_maria
    ):
        """Nem pedindo pelo id: a policy é aplicada antes do filtro."""
        with como(token_jean) as http:
            resposta = http.get(
                "/contas", params={"select": "*", "id": f"eq.{conta_da_maria}"}
            )
        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_clientes_so_traz_a_si_mesmo(self, token_jean, jean, maria):
        with como(token_jean) as http:
            resposta = http.get("/clientes", params={"select": "id"})
        assert resposta.status_code == 200
        assert [linha["id"] for linha in resposta.json()] == [jean]

    def test_transacoes_so_das_proprias_contas(
        self, token_jean, conta_do_jean, conta_da_maria
    ):
        with como(token_jean) as http:
            resposta = http.get("/transacoes", params={"select": "conta_id"})
        assert resposta.status_code == 200
        contas = {linha["conta_id"] for linha in resposta.json()}
        assert conta_da_maria not in contas


class TestEscritaDireta:
    """RNF-3.12 — nenhuma policy concede escrita: o ledger é intocável por fora."""

    def test_insert_em_transacoes_e_recusado(self, token_jean, conta_do_jean):
        with como(token_jean) as http:
            resposta = http.post(
                "/transacoes",
                json={
                    "conta_id": conta_do_jean,
                    "tipo": "deposito",
                    "valor": "1000000.00",
                    "saldo_apos": "1000000.00",
                },
            )
        assert resposta.status_code in (401, 403, 404, 405)

    def test_update_de_saldo_e_recusado(self, token_jean, conta_do_jean, banco):
        with como(token_jean) as http:
            http.patch(
                "/contas",
                params={"id": f"eq.{conta_do_jean}"},
                json={"saldo": "999999.00"},
            )
        saldo = banco.execute(
            "select saldo from contas where id = %s", (conta_do_jean,)
        ).fetchone()[0]
        assert str(saldo) == "1000.00", "saldo foi alterado por fora da API"

    def test_delete_de_conta_e_recusado(self, token_jean, conta_do_jean, banco):
        with como(token_jean) as http:
            http.delete("/contas", params={"id": f"eq.{conta_do_jean}"})
        assert banco.execute(
            "select count(*) from contas where id = %s", (conta_do_jean,)
        ).fetchone()[0] == 1


class TestFuncoesNaoExpostas:
    """As funções de movimentação não verificam titularidade — quem verifica é a
    API. Expô-las ao PostgREST permitiria depositar e sacar em conta alheia
    passando o id pela RPC."""

    @pytest.mark.parametrize(
        ("funcao", "argumentos"),
        [
            ("realizar_deposito", {"p_conta_id": 1, "p_valor": 1000}),
            ("realizar_saque", {"p_conta_id": 1, "p_valor": 1}),
            ("abrir_conta", {"p_cliente_id": 1, "p_tipo": "corrente"}),
            ("encerrar_conta", {"p_conta_id": 1}),
        ],
    )
    def test_rpc_nao_e_alcancavel(self, token_jean, funcao, argumentos):
        with como(token_jean) as http:
            resposta = http.post(f"/rpc/{funcao}", json=argumentos)
        assert resposta.status_code >= 400, (
            f"{funcao} está exposta via RPC: {resposta.status_code}"
        )

    def test_saldo_alheio_nao_muda_por_rpc(self, token_jean, conta_da_maria, banco):
        with como(token_jean) as http:
            http.post(
                "/rpc/realizar_deposito",
                json={"p_conta_id": conta_da_maria, "p_valor": 999999},
            )
        saldo = banco.execute(
            "select saldo from contas where id = %s", (conta_da_maria,)
        ).fetchone()[0]
        assert str(saldo) == "500.00"
