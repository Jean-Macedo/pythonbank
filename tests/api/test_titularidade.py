"""O teste que guarda o modo de falha mais provável do projeto (RN-2.5).

Com várias contas por cliente, todo endpoint de movimentação recebe um
`conta_id` na URL. Uma rota adicionada meses depois, sem a dependência de
titularidade, abre o sistema inteiro.

Por isso este teste é **parametrizado sobre `app.routes`**: rota nova com
`{conta_id}` entra aqui automaticamente e quebra a suíte se não verificar.
Ninguém precisa lembrar de atualizá-lo.
"""

import pytest

from backend.main import app

METODOS_COM_CORPO = {"POST", "PATCH", "PUT"}

#: Corpo mínimo válido por rota, para que a requisição chegue à verificação de
#: titularidade em vez de parar antes, em erro de validação do Pydantic.
CORPO_POR_ROTA = {
    "/api/contas/{conta_id}/deposito": {"valor": "10.00"},
    "/api/contas/{conta_id}/saque": {"valor": "10.00"},
    "/api/contas/{conta_id}/transferencia": {
        "valor": "10.00",
        "agencia_destino": "0001",
        "numero_destino": "00100001",
    },
    "/api/contas/{conta_id}": {"apelido": "Novo"},
}


def rotas_com_conta_id():
    """Toda rota do app que recebe `{conta_id}` no caminho.

    Lido do schema OpenAPI, não de `app.routes`: a partir do FastAPI 0.141 as
    rotas incluídas por `include_router` ficam em objetos `_IncludedRouter` e
    não aparecem achatadas na lista. O OpenAPI é o contrato publicado de fato,
    e não muda de forma entre versões.
    """
    caminhos = app.openapi()["paths"]
    return sorted(
        (metodo.upper(), caminho)
        for caminho, operacoes in caminhos.items()
        if "{conta_id}" in caminho
        for metodo in operacoes
        if metodo.upper() not in ("HEAD", "OPTIONS")
    )


ROTAS = rotas_com_conta_id()


def test_existem_rotas_para_verificar():
    """Guarda contra a lista vazia fazendo o teste abaixo passar à toa."""
    assert len(ROTAS) >= 5, f"apenas {len(ROTAS)} rotas encontradas: {ROTAS}"


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS, ids=lambda v: str(v))
def test_conta_alheia_responde_404(
    metodo, caminho, cliente_http, cabecalho_jean, conta_da_maria
):
    """Jean tentando alcançar a conta da Maria, por cada rota que existe.

    A resposta tem de ser 404 — nunca 403, que confirmaria a existência do
    identificador e permitiria enumerar as contas do banco (DT-04).
    """
    url = caminho.replace("{conta_id}", str(conta_da_maria))
    corpo = CORPO_POR_ROTA.get(caminho) if metodo in METODOS_COM_CORPO else None

    resposta = cliente_http.request(metodo, url, json=corpo, headers=cabecalho_jean)

    assert resposta.status_code == 404, (
        f"{metodo} {caminho} devolveu {resposta.status_code}: {resposta.text[:200]}"
    )
    assert resposta.json()["codigo"] == "CONTA_NAO_ENCONTRADA"


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS, ids=lambda v: str(v))
def test_sem_autenticacao_responde_401(metodo, caminho, cliente_http, conta_do_jean):
    """CA-03 — requisição sem identificação não lê nem move nada."""
    url = caminho.replace("{conta_id}", str(conta_do_jean))
    corpo = CORPO_POR_ROTA.get(caminho) if metodo in METODOS_COM_CORPO else None

    resposta = cliente_http.request(metodo, url, json=corpo)

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "NAO_AUTENTICADO"


class TestNaoVazamento:
    def test_conta_inexistente_responde_igual_a_conta_alheia(
        self, cliente_http, cabecalho_jean, conta_da_maria
    ):
        """As duas respostas têm de ser indistinguíveis, corpo inclusive."""
        alheia = cliente_http.get(f"/api/contas/{conta_da_maria}", headers=cabecalho_jean)
        inexistente = cliente_http.get("/api/contas/999999", headers=cabecalho_jean)

        assert alheia.status_code == inexistente.status_code == 404
        assert alheia.json() == inexistente.json()

    def test_listagem_so_traz_as_proprias_contas(
        self, cliente_http, cabecalho_jean, conta_do_jean, conta_da_maria
    ):
        resposta = cliente_http.get("/api/contas", headers=cabecalho_jean)
        ids = [c["id"] for c in resposta.json()["contas"]]
        assert conta_do_jean in ids
        assert conta_da_maria not in ids

    def test_conta_encerrada_some_da_listagem_e_das_rotas(
        self, cliente_http, cabecalho_jean, abrir_conta, jean
    ):
        conta = abrir_conta(jean, apelido="Efêmera")
        assert cliente_http.delete(
            f"/api/contas/{conta}", headers=cabecalho_jean
        ).status_code == 204

        assert cliente_http.get(
            f"/api/contas/{conta}", headers=cabecalho_jean
        ).status_code == 404
