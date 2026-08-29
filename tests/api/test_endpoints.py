"""Contrato da API: caminho feliz e cada código de erro (RNF-2.10)."""

from decimal import Decimal

import pytest


class TestInfraestrutura:
    def test_health_dispensa_autenticacao(self, cliente_http):
        resposta = cliente_http.get("/health")
        assert resposta.status_code == 200
        assert resposta.json()["status"] == "ok"

    def test_documentacao_abre(self, cliente_http):
        assert cliente_http.get("/docs").status_code == 200
        assert cliente_http.get("/openapi.json").status_code == 200

    def test_cors_anuncia_a_origem_configurada(self, cliente_http):
        """RNF-2.2 — sem isto o navegador bloqueia o React na F4."""
        resposta = cliente_http.options(
            "/api/contas",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resposta.headers["access-control-allow-origin"] == "http://localhost:5173"


class TestContas:
    def test_listar(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.get("/api/contas", headers=cabecalho_jean)
        assert resposta.status_code == 200
        assert resposta.json()["contas"][0]["apelido"] == "Dia a dia"

    def test_abrir(self, cliente_http, cabecalho_jean):
        resposta = cliente_http.post(
            "/api/contas",
            json={"tipo": "poupanca", "apelido": "Reserva"},
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["tipo"] == "poupanca"
        assert corpo["saldo"] == "0.00"
        assert len(corpo["numero"]) == 8

    def test_abrir_com_tipo_invalido(self, cliente_http, cabecalho_jean):
        resposta = cliente_http.post(
            "/api/contas", json={"tipo": "salario"}, headers=cabecalho_jean
        )
        assert resposta.status_code == 422

    def test_apelido_duplicado(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.post(
            "/api/contas",
            json={"tipo": "poupanca", "apelido": "dia a dia"},
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 409
        assert resposta.json()["codigo"] == "APELIDO_DUPLICADO"

    def test_limite_de_contas(self, cliente_http, cabecalho_jean, abrir_conta, jean):
        from backend.core.cliente import Cliente

        for i in range(Cliente.LIMITE_DE_CONTAS):
            abrir_conta(jean, apelido=f"Conta {i}")
        resposta = cliente_http.post(
            "/api/contas", json={"tipo": "corrente"}, headers=cabecalho_jean
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "LIMITE_DE_CONTAS"

    def test_renomear(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.patch(
            f"/api/contas/{conta_do_jean}",
            json={"apelido": "Principal"},
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 200
        assert resposta.json()["apelido"] == "Principal"

    def test_encerrar_com_saldo(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.delete(
            f"/api/contas/{conta_do_jean}", headers=cabecalho_jean
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "CONTA_NAO_ENCERRAVEL"


class TestMovimentacao:
    def test_deposito(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.post(
            f"/api/contas/{conta_do_jean}/deposito",
            json={"valor": "250.50"},
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 201
        assert resposta.json()["saldo_atual"] == "1250.50"

    def test_saque(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.post(
            f"/api/contas/{conta_do_jean}/saque",
            json={"valor": "100.00"},
            headers=cabecalho_jean,
        )
        assert resposta.json()["saldo_atual"] == "900.00"

    def test_saldo_insuficiente(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.post(
            f"/api/contas/{conta_do_jean}/saque",
            json={"valor": "99999.00"},
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "SALDO_INSUFICIENTE"

    @pytest.mark.parametrize("valor", ["0", "-10.00", "abc", "1.005"])
    def test_valor_invalido(self, cliente_http, cabecalho_jean, conta_do_jean, valor):
        resposta = cliente_http.post(
            f"/api/contas/{conta_do_jean}/deposito",
            json={"valor": valor},
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 422

    def test_transferencia_entre_contas_do_titular(
        self, cliente_http, cabecalho_jean, conta_do_jean, abrir_conta, jean, banco
    ):
        destino = abrir_conta(jean, tipo="poupanca", apelido="Reserva")
        agencia, numero = banco.execute(
            "select agencia, numero from contas where id = %s", (destino,)
        ).fetchone()

        resposta = cliente_http.post(
            f"/api/contas/{conta_do_jean}/transferencia",
            json={
                "valor": "300.00",
                "agencia_destino": agencia,
                "numero_destino": numero,
            },
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 201
        assert resposta.json()["saldo_atual"] == "700.00"

        saldo_destino = banco.execute(
            "select saldo from contas where id = %s", (destino,)
        ).fetchone()[0]
        assert saldo_destino == Decimal("300.00")

    def test_transferencia_para_destino_inexistente(
        self, cliente_http, cabecalho_jean, conta_do_jean
    ):
        resposta = cliente_http.post(
            f"/api/contas/{conta_do_jean}/transferencia",
            json={
                "valor": "10.00",
                "agencia_destino": "0001",
                "numero_destino": "99999999",
            },
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 404
        assert resposta.json()["codigo"] == "CONTA_NAO_ENCONTRADA"

    def test_transferencia_para_si_mesmo(
        self, cliente_http, cabecalho_jean, conta_do_jean, banco
    ):
        agencia, numero = banco.execute(
            "select agencia, numero from contas where id = %s", (conta_do_jean,)
        ).fetchone()
        resposta = cliente_http.post(
            f"/api/contas/{conta_do_jean}/transferencia",
            json={
                "valor": "10.00",
                "agencia_destino": agencia,
                "numero_destino": numero,
            },
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "CONTAS_IGUAIS"


class TestCorpoDaRequisicao:
    def test_conta_id_no_corpo_e_ignorado(
        self, cliente_http, cabecalho_jean, conta_do_jean, conta_da_maria, banco
    ):
        """DT-04 — a conta vem da URL. Mandar outra no corpo não muda nada."""
        cliente_http.post(
            f"/api/contas/{conta_do_jean}/deposito",
            json={"valor": "50.00", "conta_id": conta_da_maria},
            headers=cabecalho_jean,
        )
        saldo_maria = banco.execute(
            "select saldo from contas where id = %s", (conta_da_maria,)
        ).fetchone()[0]
        assert saldo_maria == Decimal("500.00")


class TestPrecisaoNaBorda:
    """DT-01 — dinheiro sai como string para não virar float no JavaScript."""

    def test_saldo_sai_como_string(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.get(
            f"/api/contas/{conta_do_jean}", headers=cabecalho_jean
        )
        assert resposta.json()["saldo"] == "1000.00"
        assert isinstance(resposta.json()["saldo"], str)

    def test_dez_centavos_tres_vezes(
        self, cliente_http, cabecalho_jean, abrir_conta, jean
    ):
        conta = abrir_conta(jean, apelido="Centavos")
        for _ in range(3):
            resposta = cliente_http.post(
                f"/api/contas/{conta}/deposito",
                json={"valor": "0.10"},
                headers=cabecalho_jean,
            )
        assert resposta.json()["saldo_atual"] == "0.30"


class TestExtrato:
    def test_lista_mais_recente_primeiro(
        self, cliente_http, cabecalho_jean, conta_do_jean
    ):
        for valor in ("10.00", "20.00", "30.00"):
            cliente_http.post(
                f"/api/contas/{conta_do_jean}/deposito",
                json={"valor": valor},
                headers=cabecalho_jean,
            )
        resposta = cliente_http.get(
            f"/api/contas/{conta_do_jean}/extrato", headers=cabecalho_jean
        )
        valores = [t["valor"] for t in resposta.json()["transacoes"]]
        assert valores[:3] == ["30.00", "20.00", "10.00"]

    def test_paginacao_por_cursor_nao_repete_nem_pula(
        self, cliente_http, cabecalho_jean, abrir_conta, jean
    ):
        conta = abrir_conta(jean, apelido="Paginada")
        for i in range(1, 11):
            cliente_http.post(
                f"/api/contas/{conta}/deposito",
                json={"valor": f"{i}.00"},
                headers=cabecalho_jean,
            )

        vistos, cursor = [], None
        for _ in range(10):  # limite de segurança contra laço infinito
            url = f"/api/contas/{conta}/extrato?limite=3"
            if cursor:
                url += f"&cursor={cursor}"
            corpo = cliente_http.get(url, headers=cabecalho_jean).json()
            vistos.extend(t["id"] for t in corpo["transacoes"])
            cursor = corpo["proximo_cursor"]
            if not cursor:
                break

        assert len(vistos) == 10
        assert len(set(vistos)) == 10, "algum lançamento repetiu entre páginas"

    def test_cursor_invalido(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.get(
            f"/api/contas/{conta_do_jean}/extrato?cursor=lixo", headers=cabecalho_jean
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "CURSOR_INVALIDO"

    def test_limite_maximo_e_imposto(self, cliente_http, cabecalho_jean, conta_do_jean):
        resposta = cliente_http.get(
            f"/api/contas/{conta_do_jean}/extrato?limite=5000", headers=cabecalho_jean
        )
        assert resposta.status_code == 422


class TestCliente:
    """RF-2.1 — `/api/me` era a única rota autenticada sem cobertura."""

    def test_devolve_o_titular_autenticado(self, cliente_http, cabecalho_jean):
        resposta = cliente_http.get("/api/me", headers=cabecalho_jean)
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["nome"] == "Jean Macedo"
        assert corpo["cpf"] == "52998224725"

    def test_cada_titular_recebe_os_proprios_dados(
        self, cliente_http, cabecalho_jean, cabecalho_maria
    ):
        jean = cliente_http.get("/api/me", headers=cabecalho_jean).json()
        maria = cliente_http.get("/api/me", headers=cabecalho_maria).json()
        assert jean["id"] != maria["id"]
        assert maria["nome"] == "Maria Souza"

    def test_sem_autenticacao(self, cliente_http):
        resposta = cliente_http.get("/api/me")
        assert resposta.status_code == 401
        assert resposta.json()["codigo"] == "NAO_AUTENTICADO"


class TestCabecalhoMalformado:
    """Falha de identificação é sempre 401, nunca 422 do Pydantic."""

    @pytest.mark.parametrize("valor", ["abc", "", "  ", "1.5", "'; drop table contas--"])
    def test_valor_invalido_devolve_401(self, cliente_http, valor):
        resposta = cliente_http.get("/api/contas", headers={"X-Cliente-Id": valor})
        assert resposta.status_code == 401
        assert resposta.json()["codigo"] == "NAO_AUTENTICADO"

    def test_cliente_inexistente_devolve_401(self, cliente_http):
        resposta = cliente_http.get("/api/contas", headers={"X-Cliente-Id": "999999"})
        assert resposta.status_code == 401


class TestSaudeDoServico:
    def test_health_confirma_o_banco(self, cliente_http):
        """Um health que não consulta o banco faria o container reportar
        `healthy` com o PostgreSQL fora (RNF-5.4)."""
        corpo = cliente_http.get("/health").json()
        assert corpo == {"status": "ok", "banco": "ok"}


class TestTipoDeContaInvalido:
    @pytest.mark.parametrize("apelido", ["   ", ""])
    def test_apelido_em_branco_vira_ausente_e_nao_erro_de_tipo(
        self, cliente_http, cabecalho_jean, apelido
    ):
        """Antes, o `check_violation` do apelido virava TIPO_DE_CONTA_INVALIDO."""
        resposta = cliente_http.post(
            "/api/contas",
            json={"tipo": "corrente", "apelido": apelido},
            headers=cabecalho_jean,
        )
        assert resposta.status_code == 201
        assert resposta.json()["apelido"] is None
