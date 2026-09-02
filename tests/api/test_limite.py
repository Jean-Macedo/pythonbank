"""Limite de requisições (RNF-3.9).

Duas proteções diferentes: força bruta no login, e automação descontrolada na
movimentação. Os testes zeram o contador entre casos — sem isso, um teste
gastaria a cota do seguinte, e a suíte passaria a depender da ordem.
"""

import uuid

import pytest

from backend.api import limite


@pytest.fixture(autouse=True)
def contador_zerado():
    """O limitador é único do processo — de propósito, senão não contaria nada.

    Isso o torna estado compartilhado entre testes, e zerar antes de cada um é o
    que impede que um consuma a cota do outro.
    """
    limite.limitador.contador.zerar()
    yield
    limite.limitador.contador.zerar()


class TestLogin:
    def test_bloqueia_depois_do_limite(self, cliente_http, usuarios):
        email = usuarios["jean"]["email"]
        corpo = {"email": email, "senha": "errada"}

        for _ in range(limite.LOGIN_POR_ORIGEM.quantidade):
            assert cliente_http.post("/auth/login", json=corpo).status_code == 401

        excedido = cliente_http.post("/auth/login", json=corpo)
        assert excedido.status_code == 429
        assert excedido.json()["codigo"] == "LIMITE_EXCEDIDO"

    def test_a_resposta_diz_quanto_esperar(self, cliente_http, usuarios):
        corpo = {"email": usuarios["jean"]["email"], "senha": "errada"}
        for _ in range(limite.LOGIN_POR_ORIGEM.quantidade + 1):
            resposta = cliente_http.post("/auth/login", json=corpo)

        assert resposta.status_code == 429
        # sem `Retry-After` o cliente insiste às cegas, que é o que o limite
        # existe para conter
        assert int(resposta.headers["Retry-After"]) > 0

    def test_a_senha_certa_tambem_conta(self, cliente_http, usuarios):
        """Contar só as falhas deixaria o atacante zerar o contador acertando
        qualquer conta pelo caminho."""
        from tests.api.conftest import SENHA

        corpo = {"email": usuarios["jean"]["email"], "senha": SENHA}
        for _ in range(limite.LOGIN_POR_ORIGEM.quantidade):
            assert cliente_http.post("/auth/login", json=corpo).status_code == 200

        assert cliente_http.post("/auth/login", json=corpo).status_code == 429

    def test_o_limite_por_email_protege_a_conta(self, cliente_http, usuarios):
        """Um atacante com muitas origens não deveria escapar do limite.

        Aqui a origem é sempre a mesma, então este teste sozinho não distingue
        as duas regras — quem distingue é `test_chaves_por_email_sao_separadas`.
        """
        alvo = usuarios["jean"]["email"]
        for _ in range(limite.LOGIN_POR_EMAIL.quantidade):
            cliente_http.post("/auth/login", json={"email": alvo, "senha": "x"})

        assert cliente_http.post(
            "/auth/login", json={"email": alvo, "senha": "x"}
        ).status_code == 429

    def test_chaves_por_email_sao_separadas(self):
        """No nível do limitador, onde dá para variar a origem de verdade."""
        limitador = limite.Limitador()
        for _ in range(limite.LOGIN_POR_EMAIL.quantidade):
            limitador.exigir("login:email:alvo@x.com", limite.LOGIN_POR_EMAIL)

        with pytest.raises(limite.LimiteExcedido):
            limitador.exigir("login:email:alvo@x.com", limite.LOGIN_POR_EMAIL)

        # outro e-mail continua livre
        limitador.exigir("login:email:outro@x.com", limite.LOGIN_POR_EMAIL)


class TestMovimentacao:
    def test_bloqueia_depois_do_limite(
        self, cliente_http, cabecalho_jean, conta_do_jean
    ):
        for _ in range(limite.MOVIMENTACAO_POR_TITULAR.quantidade):
            resposta = cliente_http.post(
                f"/api/contas/{conta_do_jean}/deposito",
                json={"valor": "1.00"}, headers=cabecalho_jean,
            )
            assert resposta.status_code == 201

        excedida = cliente_http.post(
            f"/api/contas/{conta_do_jean}/deposito",
            json={"valor": "1.00"}, headers=cabecalho_jean,
        )
        assert excedida.status_code == 429

    def test_o_limite_e_por_titular_nao_por_conta(
        self, cliente_http, cabecalho_jean, conta_do_jean, abrir_conta, jean
    ):
        """Abrir outra conta não renova a cota: quem move é a pessoa."""
        outra = abrir_conta(jean, tipo="poupanca", apelido="Outra")

        for _ in range(limite.MOVIMENTACAO_POR_TITULAR.quantidade):
            cliente_http.post(
                f"/api/contas/{conta_do_jean}/deposito",
                json={"valor": "1.00"}, headers=cabecalho_jean,
            )

        assert cliente_http.post(
            f"/api/contas/{outra}/deposito",
            json={"valor": "1.00"}, headers=cabecalho_jean,
        ).status_code == 429

    def test_um_titular_nao_gasta_a_cota_do_outro(
        self, cliente_http, cabecalho_jean, cabecalho_maria, conta_do_jean,
        conta_da_maria,
    ):
        for _ in range(limite.MOVIMENTACAO_POR_TITULAR.quantidade + 1):
            cliente_http.post(
                f"/api/contas/{conta_do_jean}/deposito",
                json={"valor": "1.00"}, headers=cabecalho_jean,
            )

        assert cliente_http.post(
            f"/api/contas/{conta_da_maria}/deposito",
            json={"valor": "1.00"}, headers=cabecalho_maria,
        ).status_code == 201

    def test_a_leitura_nao_e_limitada(
        self, cliente_http, cabecalho_jean, conta_do_jean
    ):
        """O limite protege escrita. Bloquear consulta de saldo puniria quem
        recarrega a página."""
        for _ in range(limite.MOVIMENTACAO_POR_TITULAR.quantidade + 5):
            assert cliente_http.get(
                "/api/contas", headers=cabecalho_jean
            ).status_code == 200


class TestOrigemDaRequisicao:
    """`X-Forwarded-For` só vale com proxy declarado.

    Aceitá-lo por padrão seria pior que não ter limite: cada requisição traria
    uma origem forjada diferente, e a proteção estaria desligada aparentando
    existir.
    """

    def _pedido(self, cabecalhos, host="1.2.3.4"):
        from starlette.datastructures import Headers
        from starlette.requests import Request

        escopo = {
            "type": "http",
            "headers": Headers(cabecalhos).raw,
            "client": (host, 1234),
        }
        return Request(escopo)

    def test_sem_proxy_declarado_o_cabecalho_e_ignorado(self):
        from backend.config import Configuracao

        cfg = Configuracao(database_url="x", supabase_anon_key="k",
                           confiar_em_proxy=False)
        pedido = self._pedido({"X-Forwarded-For": "9.9.9.9"})
        assert limite.endereco_de(pedido, cfg) == "1.2.3.4"

    def test_com_proxy_declarado_o_cabecalho_vale(self):
        from backend.config import Configuracao

        cfg = Configuracao(database_url="x", supabase_anon_key="k",
                           confiar_em_proxy=True)
        pedido = self._pedido({"X-Forwarded-For": "9.9.9.9, 10.0.0.1"})
        assert limite.endereco_de(pedido, cfg) == "9.9.9.9"

    def test_o_padrao_e_nao_confiar(self):
        from backend.config import Configuracao

        cfg = Configuracao(database_url="x", supabase_anon_key="k")
        assert cfg.confiar_em_proxy is False


class TestContador:
    def test_a_janela_zera_o_total(self):
        contador = limite.ContadorEmMemoria()
        chave = uuid.uuid4().hex

        total, _ = contador.registrar(chave, janela_segundos=0)
        assert total == 1
        # janela de zero segundos: a próxima já cai numa janela nova
        total, _ = contador.registrar(chave, janela_segundos=0)
        assert total == 1

    def test_chaves_diferentes_nao_se_misturam(self):
        contador = limite.ContadorEmMemoria()
        assert contador.registrar("a", 60)[0] == 1
        assert contador.registrar("b", 60)[0] == 1

    def test_conta_de_forma_crescente(self):
        contador = limite.ContadorEmMemoria()
        totais = [contador.registrar("x", 60)[0] for _ in range(5)]
        assert totais == [1, 2, 3, 4, 5]

    def test_o_dicionario_nao_cresce_para_sempre(self):
        """Sem a limpeza, cada origem nova deixaria uma entrada permanente e um
        ataque distribuído viraria consumo de memória em vez de bloqueio."""
        contador = limite.ContadorEmMemoria()
        for i in range(200):
            contador.registrar(f"efemera-{i}", janela_segundos=0)

        contador._ultima_limpeza = 0  # força a próxima limpeza
        contador.registrar("gatilho", 60)
        assert len(contador._contagens) < 200
