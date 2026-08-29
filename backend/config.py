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

    ambiente: str = Field(default="desenvolvimento")

    autenticacao_stub: bool = Field(
        default=False,
        description="Resolve o cliente pelo cabeçalho X-Cliente-Id em vez de um "
        "JWT. Existe só até a Fase 3 e nunca pode ir para produção.",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def dividir_lista(cls, valor):
        """Aceita `a,b,c` além de lista JSON, que é o formato natural em .env."""
        if isinstance(valor, str) and not valor.strip().startswith("["):
            return [item.strip() for item in valor.split(",") if item.strip()]
        return valor

    @property
    def e_producao(self) -> bool:
        return self.ambiente.lower() in ("producao", "produção", "production")

    def validar_coerencia(self) -> None:
        """Combinações que não podem existir, checadas na subida do app."""
        if self.e_producao and self.autenticacao_stub:
            raise RuntimeError(
                "AUTENTICACAO_STUB não pode estar ligada em produção: ela aceita "
                "qualquer cliente informado no cabeçalho, sem verificar nada."
            )


@lru_cache
def configuracao() -> Configuracao:
    cfg = Configuracao()
    cfg.validar_coerencia()
    return cfg
