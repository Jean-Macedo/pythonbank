"""Conexão com o PostgreSQL.

O PRD previa `supabase-py`. Uso `psycopg` direto porque o backend tem acesso ao
banco: o cliente HTTP do Supabase existe para navegadores, e passar por PostgREST
acrescentaria um salto de rede a cada chamada sem dar nada em troca. As funções
PL/pgSQL da Fase 1 são invocadas com `select fn(...)`, e o pool de conexões
importa mais do que a conveniência do SDK.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg_pool import ConnectionPool

from backend.config import configuracao

_pool: ConnectionPool | None = None


def abrir_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=configuracao().database_url,
            min_size=1,
            max_size=10,
            open=True,
            # falha rápido se o banco não responde, em vez de pendurar a requisição
            timeout=5,
        )
    return _pool


def fechar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def conexao() -> Iterator[psycopg.Connection]:
    """Empresta uma conexão do pool.

    `autocommit` porque cada chamada é uma função PL/pgSQL que já é atômica por
    si (DT-02) — envolver em outra transação não acrescenta garantia nenhuma.
    """
    with abrir_pool().connection() as con:
        con.autocommit = True
        yield con
