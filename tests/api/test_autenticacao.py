"""Cadastro, entrada, renovação e validação de token (RN-3.1 a RF-3.4)."""

import random
import time
import types
import uuid

import jwt
import pytest

from backend.config import configuracao
from tests.api.conftest import SENHA, gerar_cpf


def novo_registro(rng: random.Random, **sobrescritas) -> dict:
    marca = uuid.uuid4().hex[:8]
    dados = {
        "nome": "Pessoa Teste",
        "cpf": gerar_cpf(rng),
        "email": f"pessoa-{marca}@exemplo-teste.com",
        "telefone": "11912345678",
        "data_nascimento": "20/05/1990",
        "senha": SENHA,
    }
    dados.update(sobrescritas)
    return dados


@pytest.fixture
def rng():
    return random.Random(uuid.uuid4().hex)


class TestRegistro:
    def test_cria_titular_e_conta_inicial(self, cliente_http, rng, banco):
        """RF-3.3 — usuário, titular e conta nascem juntos."""
        resposta = cliente_http.post("/auth/registro", json=novo_registro(rng))
        assert resposta.status_code == 201

        corpo = resposta.json()
        assert corpo["sessao"]["access_token"]

        conta = banco.execute(
            "select cliente_id, saldo, apelido from contas where id = %s",
            (corpo["conta_id"],),
        ).fetchone()
        assert conta[0] == corpo["cliente_id"]
        assert conta[1] == 0

    def test_token_devolvido_ja_funciona(self, cliente_http, rng):
        corpo = cliente_http.post("/auth/registro", json=novo_registro(rng)).json()
        cabecalho = {"Authorization": f"Bearer {corpo['sessao']['access_token']}"}
        assert cliente_http.get("/api/me", headers=cabecalho).status_code == 200

    def test_validacao_do_dominio_e_aplicada(self, cliente_http, rng):
        """O CPF é rejeitado pelos dígitos verificadores, não pelo formato."""
        resposta = cliente_http.post(
            "/auth/registro", json=novo_registro(rng, cpf="12345678900")
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == "CPF_INVALIDO"

    @pytest.mark.parametrize(
        ("campo", "valor", "codigo"),
        [
            ("email", "sem-arroba", "EMAIL_INVALIDO"),
            ("data_nascimento", "31/02/1990", "DATA_NASCIMENTO_INVALIDA"),
            ("data_nascimento", "10/03/2999", "DATA_NASCIMENTO_FUTURA"),
            ("nome", "   ", "NOME_INVALIDO"),
        ],
    )
    def test_cada_erro_de_cadastro_tem_codigo_proprio(
        self, cliente_http, rng, campo, valor, codigo
    ):
        resposta = cliente_http.post(
            "/auth/registro", json=novo_registro(rng, **{campo: valor})
        )
        assert resposta.status_code == 422
        assert resposta.json()["codigo"] == codigo

    def test_cpf_duplicado(self, cliente_http, rng):
        dados = novo_registro(rng)
        assert cliente_http.post("/auth/registro", json=dados).status_code == 201

        outro = novo_registro(rng, cpf=dados["cpf"])
        resposta = cliente_http.post("/auth/registro", json=outro)
        assert resposta.status_code == 409
        assert resposta.json()["codigo"] == "CPF_DUPLICADO"

    def test_cadastro_recusado_nao_deixa_usuario_orfao(self, cliente_http, rng, banco):
        """A compensação existe para isto: um login que não leva a lugar nenhum.

        Sem remover o usuário do GoTrue, uma segunda tentativa com o mesmo e-mail
        bateria em "já cadastrado" para sempre, sem nunca ter criado o titular.
        """
        dados = novo_registro(rng)
        cliente_http.post("/auth/registro", json=dados)

        # mesmo e-mail, CPF já em uso: falha depois de o usuário ser criado
        conflito = novo_registro(rng, cpf=dados["cpf"])
        email = conflito["email"]
        assert cliente_http.post("/auth/registro", json=conflito).status_code == 409

        # o e-mail tem de continuar livre: nenhum titular ficou com ele
        assert banco.execute(
            "select count(*) from clientes where email = %s", (email,)
        ).fetchone()[0] == 0

        retomada = novo_registro(rng, email=email)
        assert cliente_http.post("/auth/registro", json=retomada).status_code == 201

    def test_senha_curta_e_recusada(self, cliente_http, rng):
        resposta = cliente_http.post(
            "/auth/registro", json=novo_registro(rng, senha="curta")
        )
        assert resposta.status_code == 422


class TestLogin:
    def test_entra_com_credencial_correta(self, cliente_http, usuarios):
        resposta = cliente_http.post(
            "/auth/login", json={"email": usuarios["jean"]["email"], "senha": SENHA}
        )
        assert resposta.status_code == 200
        assert resposta.json()["tipo"] == "bearer"

    @pytest.mark.parametrize("senha", ["errada", "", SENHA + "x"])
    def test_senha_incorreta(self, cliente_http, usuarios, senha):
        resposta = cliente_http.post(
            "/auth/login", json={"email": usuarios["jean"]["email"], "senha": senha}
        )
        assert resposta.status_code == 401

    def test_email_inexistente_responde_igual_a_senha_errada(
        self, cliente_http, usuarios
    ):
        """A diferença entre as duas revelaria quais e-mails têm conta."""
        inexistente = cliente_http.post(
            "/auth/login",
            json={"email": f"{uuid.uuid4().hex}@exemplo-teste.com", "senha": SENHA},
        )
        errada = cliente_http.post(
            "/auth/login", json={"email": usuarios["jean"]["email"], "senha": "errada"}
        )
        assert inexistente.status_code == errada.status_code == 401
        assert inexistente.json() == errada.json()


class TestRenovacao:
    def test_refresh_devolve_acesso_novo(self, cliente_http, usuarios):
        sessao = cliente_http.post(
            "/auth/login", json={"email": usuarios["jean"]["email"], "senha": SENHA}
        ).json()

        renovada = cliente_http.post(
            "/auth/refresh", json={"refresh_token": sessao["refresh_token"]}
        )
        assert renovada.status_code == 200

        cabecalho = {"Authorization": f"Bearer {renovada.json()['access_token']}"}
        assert cliente_http.get("/api/me", headers=cabecalho).status_code == 200

    def test_refresh_invalido(self, cliente_http):
        resposta = cliente_http.post(
            "/auth/refresh", json={"refresh_token": "nao-e-um-token"}
        )
        assert resposta.status_code == 401


class TestValidacaoDoToken:
    def test_token_expirado(self, cliente_http, usuarios):
        """Assinatura válida não basta: `exp` é verificado."""
        token = usuarios["jean"]["token"]
        conteudo = jwt.decode(token, options={"verify_signature": False})
        conteudo["exp"] = 1000000000  # 2001
        falsificado = jwt.encode(conteudo, "qualquer-segredo", algorithm="HS256")

        resposta = cliente_http.get(
            "/api/contas", headers={"Authorization": f"Bearer {falsificado}"}
        )
        assert resposta.status_code == 401

    def test_token_assinado_por_outra_chave(self, cliente_http, usuarios):
        """O caso que importa: alguém forja o conteúdo e assina com o que tem.

        Um `sub` de outro titular, assinado com uma chave que não é a do
        Supabase, não pode virar sessão.
        """
        conteudo = jwt.decode(
            usuarios["jean"]["token"], options={"verify_signature": False}
        )
        conteudo["sub"] = usuarios["maria"]["auth_user_id"]
        forjado = jwt.encode(conteudo, "segredo-do-atacante", algorithm="HS256")

        resposta = cliente_http.get(
            "/api/contas", headers={"Authorization": f"Bearer {forjado}"}
        )
        assert resposta.status_code == 401

    def test_token_sem_assinatura_alg_none(self, cliente_http, usuarios):
        """`alg: none` é o ataque clássico contra validação mal feita."""
        conteudo = jwt.decode(
            usuarios["jean"]["token"], options={"verify_signature": False}
        )
        inseguro = jwt.encode(conteudo, key="", algorithm="none")

        resposta = cliente_http.get(
            "/api/contas", headers={"Authorization": f"Bearer {inseguro}"}
        )
        assert resposta.status_code == 401


class TestCadastroIncompleto:
    def test_token_valido_sem_titular(self, cliente_http, banco, usuarios):
        """Usuário existe no GoTrue mas o titular não: 403, não 401.

        A ação de quem recebe é diferente — concluir o cadastro, não entrar de
        novo — então o código também tem de ser.
        """
        auth_id = usuarios["maria"]["auth_user_id"]
        banco.execute("delete from clientes where auth_user_id = %s", (auth_id,))
        try:
            resposta = cliente_http.get(
                "/api/me",
                headers={"Authorization": f"Bearer {usuarios['maria']['token']}"},
            )
            assert resposta.status_code == 403
            assert resposta.json()["codigo"] == "CADASTRO_INCOMPLETO"
        finally:
            banco.execute(
                """
                insert into clientes
                    (auth_user_id, nome, cpf, email, telefone, data_nascimento)
                values (%s, 'Maria Souza', %s, %s, '21998765432', '1988-11-22')
                """,
                (auth_id, gerar_cpf(random.Random(auth_id)), usuarios["maria"]["email"]),
            )


class TestEmissorDoToken:
    """O `iss` precisa ser verificado com uma assinatura *válida*.

    A primeira versão destes testes forjava o token com HS256 e uma chave
    qualquer. Ele passava — mas pela lista de algoritmos, não pelo emissor:
    desativar a verificação de `iss` não o fazia falhar. Um teste que passa pelo
    motivo errado é pior que teste nenhum, porque dá confiança falsa.

    Aqui a assinatura é legítima do ponto de vista da validação: geramos um par
    de chaves ES256 e apontamos o JWKS para a nossa chave pública. Assim o único
    motivo possível de recusa é a claim.
    """

    @staticmethod
    def _token_assinado(chave_privada, **claims):
        conteudo = {
            "sub": "11111111-1111-1111-1111-111111111111",
            "aud": "authenticated",
            "iss": f"{configuracao().supabase_url}/auth/v1",
            "exp": int(time.time()) + 3600,
        }
        conteudo.update(claims)
        return jwt.encode(conteudo, chave_privada, algorithm="ES256")

    @pytest.fixture
    def jwks_proprio(self, monkeypatch):
        """Substitui o JWKS por uma chave que controlamos."""
        from cryptography.hazmat.primitives.asymmetric import ec

        from backend.infra import autenticacao

        privada = ec.generate_private_key(ec.SECP256R1())

        class JWKSFalso:
            def get_signing_key_from_jwt(self, token):
                return types.SimpleNamespace(key=privada.public_key())

        autenticacao.limpar_cache_jwks()
        monkeypatch.setattr(autenticacao, "_jwks", JWKSFalso())
        yield privada
        autenticacao.limpar_cache_jwks()

    def test_emissor_correto_e_aceito(self, jwks_proprio):
        """Controle: sem ele, os testes abaixo passariam por qualquer motivo."""
        from backend.infra.autenticacao import validar_token

        identidade = validar_token(self._token_assinado(jwks_proprio))
        assert identidade.auth_user_id == "11111111-1111-1111-1111-111111111111"

    def test_emissor_diferente_e_recusado(self, jwks_proprio):
        from backend.infra.autenticacao import validar_token

        token = self._token_assinado(
            jwks_proprio, iss="https://outro-projeto.supabase.co/auth/v1"
        )
        with pytest.raises(jwt.InvalidIssuerError):
            validar_token(token)

    def test_sem_emissor_e_recusado(self, jwks_proprio):
        from backend.infra.autenticacao import validar_token

        conteudo = {
            "sub": "x",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(conteudo, jwks_proprio, algorithm="ES256")
        with pytest.raises(jwt.MissingRequiredClaimError):
            validar_token(token)

    def test_audiencia_diferente_e_recusada(self, jwks_proprio):
        from backend.infra.autenticacao import validar_token

        with pytest.raises(jwt.InvalidAudienceError):
            validar_token(self._token_assinado(jwks_proprio, aud="anon"))


class TestServicoIndisponivel:
    def test_jwks_fora_do_ar_devolve_503(self, cliente_http, usuarios, monkeypatch):
        """Indisponibilidade não é falha de credencial.

        Um 401 mandaria a pessoa fazer login — que também não funcionaria — e
        esconderia a queda do serviço atrás de um erro de token.
        """
        from jwt import PyJWKClient

        from backend.infra import autenticacao

        autenticacao.limpar_cache_jwks()
        monkeypatch.setattr(
            autenticacao,
            "_jwks",
            PyJWKClient("http://127.0.0.1:1/indisponivel/jwks.json", cache_keys=False),
        )
        try:
            resposta = cliente_http.get(
                "/api/contas",
                headers={"Authorization": f"Bearer {usuarios['jean']['token']}"},
            )
            assert resposta.status_code == 503
            assert resposta.json()["codigo"] == "AUTENTICACAO_INDISPONIVEL"
        finally:
            autenticacao.limpar_cache_jwks()

    def test_volta_a_funcionar_depois(self, cliente_http, cabecalho_jean):
        """O cache é reconstruído: a queda não deixa a sessão quebrada."""
        assert cliente_http.get("/api/me", headers=cabecalho_jean).status_code == 200


class TestEmissorSeparadoDoEndereco:
    """O `iss` do token e o endereço de rede do Auth são coisas diferentes.

    Descoberto ao conteinerizar: o GoTrue carimba nos tokens o endereço que ele
    conhece (`127.0.0.1:54321`), e o backend em container o alcança por outro
    (`host.docker.internal`). Derivar o emissor da URL de conexão fazia o login
    funcionar e **toda** requisição autenticada seguinte devolver 401 — sintoma
    confuso, porque o token estava perfeito.
    """

    def test_por_padrao_deriva_da_url(self):
        from backend.config import Configuracao

        cfg = Configuracao(
            database_url="x", supabase_url="http://exemplo:54321",
            supabase_anon_key="k",
        )
        assert cfg.emissor_esperado == "http://exemplo:54321/auth/v1"

    def test_emissor_explicito_vence_a_url(self):
        """O caso do container: alcança por um endereço, espera outro."""
        from backend.config import Configuracao

        cfg = Configuracao(
            database_url="x",
            supabase_url="http://host.docker.internal:54321",
            supabase_issuer="http://127.0.0.1:54321",
            supabase_anon_key="k",
        )
        assert cfg.emissor_esperado == "http://127.0.0.1:54321/auth/v1"

    def test_aceita_emissor_ja_completo(self):
        from backend.config import Configuracao

        cfg = Configuracao(
            database_url="x", supabase_url="http://a:1",
            supabase_issuer="http://b:2/auth/v1", supabase_anon_key="k",
        )
        assert cfg.emissor_esperado == "http://b:2/auth/v1"

    def test_barra_final_nao_duplica(self):
        from backend.config import Configuracao

        cfg = Configuracao(
            database_url="x", supabase_url="http://a:1/", supabase_anon_key="k"
        )
        assert cfg.emissor_esperado == "http://a:1/auth/v1"
