"""Instância do FastAPI: middlewares, tratamento de erro e rotas.

O FastAPI é casca de transporte. Recebe HTTP, delega ao domínio, persiste via
repositório, traduz erro em status. Nenhuma regra de negócio nasce aqui.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import contas, extrato, movimentacao
from backend.api.deps import NaoAutenticado, get_cliente_atual
from backend.config import configuracao
from backend.core.erros import ErroDeDominio
from backend.infra.database import abrir_pool, fechar_pool
from backend.infra.repositorios import ClienteLido
from backend.schemas import ClienteOut, ErroOut

log = logging.getLogger("banco")

#: Tradução de código de domínio para status HTTP (RF-2.4).
#: Regra de negócio violada é 422; ausência é 404; conflito de unicidade é 409.
#: O padrão é 422 — um erro de domínio novo nunca deve virar 500 por esquecimento.
STATUS_POR_CODIGO = {
    "NAO_AUTENTICADO": 401,
    "CONTA_NAO_ENCONTRADA": 404,
    "CPF_DUPLICADO": 409,
    "APELIDO_DUPLICADO": 409,
}
STATUS_PADRAO = 422


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    cfg = configuracao()
    cfg.validar_coerencia()
    if cfg.autenticacao_stub:
        log.warning(
            "AUTENTICACAO_STUB ligada: o cliente vem do cabeçalho X-Cliente-Id "
            "sem verificação. Isso existe só até a Fase 3."
        )
    abrir_pool()
    yield
    fechar_pool()


app = FastAPI(
    title="Banco Jean",
    version="0.2.0",
    summary="API de contas e movimentação",
    lifespan=ciclo_de_vida,
)

# RNF-2.2 — sem isto o navegador bloqueia o React na primeira requisição.
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracao().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErroDeDominio)
async def tratar_erro_de_dominio(request: Request, erro: ErroDeDominio):
    """Ponto único de tradução: nenhum handler decide status por conta própria.

    Assim, um erro de domínio criado no futuro já sai com formato e status
    coerentes sem que ninguém precise lembrar de tratá-lo.
    """
    return JSONResponse(
        status_code=STATUS_POR_CODIGO.get(erro.codigo, STATUS_PADRAO),
        content=ErroOut(codigo=erro.codigo, mensagem=erro.mensagem).model_dump(),
    )


@app.get("/health", tags=["infraestrutura"])
def health():
    """Sem autenticação — usado pelo healthcheck do Docker na Fase 5."""
    return {"status": "ok"}


@app.get("/api/me", response_model=ClienteOut, tags=["cliente"])
def eu(cliente: ClienteLido = Depends(get_cliente_atual)):
    return ClienteOut(
        id=cliente.id,
        nome=cliente.nome,
        cpf=cliente.cpf,
        email=cliente.email,
        telefone=cliente.telefone,
        data_nascimento=cliente.data_nascimento,
    )


app.include_router(contas.router)
app.include_router(movimentacao.router)
app.include_router(extrato.router)

__all__ = ["app", "NaoAutenticado"]
