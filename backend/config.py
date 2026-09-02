"""Configuração da aplicação (RNF-2.5).

Tudo vem de variáveis de ambiente. A aplicação **falha ao subir** se faltar
alguma obrigatória, em vez de rodar com valor vazio e quebrar na primeira
requisição.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = Field(
        ...,
        description="DSN do PostgreSQL. Sem padrão de propósito: subir sem "
        "saber contra qual banco é pior do que não subir.",
    )

    # NoDecode: sem ele o pydantic-settings tenta ler o valor como JSON antes
    # de qualquer validator, e `a,b` quebra o parse.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- Supabase Auth (Fase 3) ---
    supabase_url: str = Field(
        default="http://127.0.0.1:54321",
        description="Gateway do Supabase. O JWKS e o GoTrue ficam sob /auth/v1.",
    )
    supabase_issuer: str = Field(
        default="",
        description="Emissor esperado no JWT. Vazio significa derivar de "
        "`supabase_url`, o que só vale quando o backend alcança o Auth pelo "
        "mesmo endereço que o GoTrue carimba nos tokens.",
    )

    supabase_anon_key: str = Field(
        default="",
        description="Chave pública, usada como `apikey` nas rotas de auth. "
        "Não concede acesso a dado nenhum por si só — quem decide é a RLS.",
    )
    supabase_service_role_key: str = Field(
        default="",
        description="Chave administrativa. Existe apenas no backend e nunca "
        "chega ao frontend (RN-3.8).",
    )

    ambiente: str = Field(default="desenvolvimento")

    autenticacao_stub: bool = Field(
        default=False,
        description="OBSOLETO desde a Fase 3, quando a validação de JWT entrou. "
        "Mantido só para que um .env antigo com ele ligado falhe alto, em vez "
        "de a aplicação subir aceitando qualquer cabeçalho.",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def dividir_lista(cls, valor):
        """Aceita `a,b,c` além de lista JSON, que é o formato natural em .env."""
        if isinstance(valor, str) and not valor.strip().startswith("["):
            return [item.strip() for item in valor.split(",") if item.strip()]
        return valor

    @property
    def emissor_esperado(self) -> str:
        """O `iss` que os tokens devem trazer.

        **Não é o mesmo que `supabase_url`.** Um é identidade pública — o que o
        GoTrue carimba — e o outro é endereço de rede, por onde este processo
        alcança o serviço. Em container os dois divergem: o GoTrue estampa
        `127.0.0.1:54321` e o backend chega nele por `host.docker.internal`.

        Tratá-los como um só faz toda requisição autenticada falhar com 401,
        depois de o login ter funcionado — sintoma confuso, porque o token está
        perfeito.
        """
        base = self.supabase_issuer or self.supabase_url
        return f"{base.rstrip('/')}/auth/v1" if not base.endswith("/auth/v1") else base

    @property
    def e_producao(self) -> bool:
        return self.ambiente.lower() in ("producao", "produção", "production")

    def validar_coerencia(self) -> None:
        """Combinações que não podem existir, checadas na subida do app."""
        if self.autenticacao_stub:
            raise RuntimeError(
                "AUTENTICACAO_STUB foi removida na Fase 3, quando a validação de "
                "JWT entrou. Remova a variável do .env — deixá-la ligada sugere "
                "que a autenticação está desativada, e não está."
            )
        if not self.supabase_anon_key:
            raise RuntimeError(
                "SUPABASE_ANON_KEY é obrigatória: sem ela as rotas de cadastro e "
                "login não conseguem falar com o serviço de autenticação."
            )
        if self.e_producao and self.supabase_url.startswith("http://"):
            raise RuntimeError(
                "SUPABASE_URL sem TLS em produção: o token trafegaria em claro."
            )


@lru_cache
def configuracao() -> Configuracao:
    cfg = Configuracao()
    cfg.validar_coerencia()
    return cfg
