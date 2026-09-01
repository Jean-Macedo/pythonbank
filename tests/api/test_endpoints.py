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

    def test_devolve_o_titular_autenticado(
        self, cliente_http, cabecalho_jean, usuarios, banco, jean
    ):
        resposta = cliente_http.get("/api/me", headers=cabecalho_jean)
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["id"] == jean
        assert corpo["nome"] == "Jean Macedo"
        assert corpo["email"] == usuarios["jean"]["email"]
        # o CPF é gerado por sessão; o que importa é ser o do titular do token
        esperado = banco.execute(
            "select cpf from clientes where id = %s", (jean,)
        ).fetchone()[0]
        assert corpo["cpf"] == esperado

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

    @pytest.mark.parametrize(
        "valor",
        [
            "abc",                      # não é um token
            "Bearer",                   # sem o token
            "Bearer ",                  # token vazio
            "Bearer abc.def.ghi",       # três partes, assinatura inválida
            "Basic dXNlcjpwYXNz",       # esquema errado
            "'; drop table contas--",
        ],
    )
    def test_autorizacao_invalida_devolve_401(self, cliente_http, valor):
        resposta = cliente_http.get("/api/contas", headers={"Authorization": valor})
        assert resposta.status_code == 401
        assert resposta.json()["codigo"] == "NAO_AUTENTICADO"

    def test_token_sem_prefixo_bearer(self, cliente_http, usuarios):
        """O token cru, sem `Bearer`, não vale."""
        resposta = cliente_http.get(
            "/api/contas", headers={"Authorization": usuarios["jean"]["token"]}
        )
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


class TestErroDeValidacaoDoSchema:
    """A validação do Pydantic precisa sair no formato de erro da aplicação.

    Sem tradução, ela sai como `{"detail": [...]}` — formato do FastAPI — e o
    frontend, que espera `{codigo, mensagem}`, exibe "não foi possível completar
    a operação". A pessoa fica sem saber qual campo recusar. Encontrado testando
    a interface na mão.
    """

    def test_campo_invalido_nomeia_o_campo(self, cliente_http):
        resposta = cliente_http.post(
            "/auth/registro",
            json={
                "nome": "X", "cpf": "52998224725", "email": "x@x.com",
                "telefone": "11987654321", "data_nascimento": "10/03/1995",
                "senha": "curta",
            },
        )
        assert resposta.status_code == 422
        corpo = resposta.json()
        assert corpo["codigo"] == "DADOS_INVALIDOS"
        assert "senha" in corpo["mensagem"]

    def test_nunca_devolve_o_formato_do_fastapi(self, cliente_http, cabecalho_jean):
        """`detail` não pode vazar: o frontend decide pelo `codigo`."""
        resposta = cliente_http.post(
            "/api/contas", json={"tipo": 123}, headers=cabecalho_jean
        )
        assert resposta.status_code == 422
        assert "detail" not in resposta.json()
        assert set(resposta.json()) == {"codigo", "mensagem"}

    def test_varios_campos_invalidos_sao_listados(self, cliente_http):
        resposta = cliente_http.post(
            "/auth/registro",
            json={"nome": "X", "cpf": "1", "email": "x@x.com",
                  "telefone": "1", "data_nascimento": "10/03/1995", "senha": "a"},
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "DADOS_INVALIDOS"


class TestTelefoneFormatado:
    """Escrever telefone com parênteses e hífen é a forma natural.

    O CPF já era normalizado; o telefone não, e recusava `(11) 98765-4321` — o
    sistema exigindo que a pessoa aprenda o formato interno dele.
    """

    @pytest.mark.parametrize(
        "digitado",
        ["(11) 98765-4321", "11 98765-4321", "11987654321", "11-98765-4321"],
    )
    def test_aceita_e_normaliza(self, cliente_http, digitado, banco):
        import random
        import uuid

        from tests.api.conftest import SENHA, gerar_cpf

        resposta = cliente_http.post(
            "/auth/registro",
            json={
                "nome": "Pessoa", "cpf": gerar_cpf(random.Random(uuid.uuid4().hex)),
                "email": f"tel-{uuid.uuid4().hex[:8]}@exemplo-teste.com",
                "telefone": digitado, "data_nascimento": "10/03/1995",
                "senha": SENHA,
            },
        )
        assert resposta.status_code == 201, resposta.text
        guardado = banco.execute(
            "select telefone from clientes where id = %s",
            (resposta.json()["cliente_id"],),
        ).fetchone()[0]
        assert guardado == "11987654321"


class TestCpfComMascara:
    """O CPF chega da tela com máscara; recusar por comprimento seria dizer
    "confira o campo CPF" para um CPF correto."""

    @pytest.mark.parametrize(
        "molde", ["{0}", "{1}.{2}.{3}-{4}", "{1} {2} {3} {4}", "{1}.{2}.{3}/{4}"]
    )
    def test_aceita_qualquer_separador(self, cliente_http, banco, molde):
        import random
        import uuid

        from tests.api.conftest import SENHA, gerar_cpf

        cru = gerar_cpf(random.Random(uuid.uuid4().hex))
        digitado = molde.format(cru, cru[:3], cru[3:6], cru[6:9], cru[9:])

        resposta = cliente_http.post(
            "/auth/registro",
            json={
                "nome": "Pessoa", "cpf": digitado,
                "email": f"cpf-{uuid.uuid4().hex[:8]}@exemplo-teste.com",
                "telefone": "11987654321", "data_nascimento": "10/03/1995",
                "senha": SENHA,
            },
        )
        assert resposta.status_code == 201, f"{digitado}: {resposta.text}"
        guardado = banco.execute(
            "select cpf from clientes where id = %s", (resposta.json()["cliente_id"],)
        ).fetchone()[0]
        assert guardado == cru
