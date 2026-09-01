"""Instância do FastAPI: middlewares, tratamento de erro e rotas.

O FastAPI é casca de transporte. Recebe HTTP, delega ao domínio, persiste via
repositório, traduz erro em status. Nenhuma regra de negócio nasce aqui.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import auth, contas, extrato, movimentacao
from backend.api.deps import NaoAutenticado, get_cliente_atual
from backend.config import configuracao
from backend.core.erros import ErroDeDominio
from backend.infra.autenticacao import ErroDeAutenticacao, ServicoIndisponivel
from backend.infra.database import abrir_pool, conexao, fechar_pool
from backend.infra.repositorios import ClienteLido
from backend.schemas import ClienteOut, ErroOut

log = logging.getLogger("banco")

#: Tradução de código de domínio para status HTTP (RF-2.4).
#: Regra de negócio violada é 422; ausência é 404; conflito de unicidade é 409.
#: O padrão é 422 — um erro de domínio novo nunca deve virar 500 por esquecimento.
STATUS_POR_CODIGO = {
    "NAO_AUTENTICADO": 401,
    "CADASTRO_INCOMPLETO": 403,
    "EMAIL_JA_CADASTRADO": 409,
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
    version="0.3.0",
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


#: Nome do campo como a pessoa o conhece na tela, não como o schema o chama.
ROTULO_DO_CAMPO = {
    "nome": "nome",
    "cpf": "CPF",
    "email": "e-mail",
    "telefone": "telefone",
    "data_nascimento": "data de nascimento",
    "senha": "senha",
    "valor": "valor",
    "tipo": "tipo de conta",
    "apelido": "apelido",
    "agencia_destino": "agência de destino",
    "numero_destino": "conta de destino",
    "limite": "limite",
    "cursor": "paginação",
}


@app.exception_handler(RequestValidationError)
async def tratar_erro_de_validacao(request: Request, erro: RequestValidationError):
    """Converte a validação do Pydantic para o formato de erro da aplicação.

    Sem isto, toda falha de schema sai como `{"detail": [...]}` — formato do
    FastAPI, que o frontend não reconhece e exibe como "não foi possível
    completar a operação". A pessoa fica sem saber qual campo recusar.
    """
    problemas = erro.errors()
    campos = []
    for problema in problemas:
        partes = [p for p in problema["loc"] if p not in ("body", "query", "path")]
        if partes:
            nome = str(partes[-1])
            campos.append(ROTULO_DO_CAMPO.get(nome, nome))

    if campos:
        unicos = list(dict.fromkeys(campos))
        alvo = unicos[0] if len(unicos) == 1 else ", ".join(unicos)
        mensagem = f"Confira o campo {alvo}." if len(unicos) == 1 else (
            f"Confira estes campos: {alvo}."
        )
    else:
        mensagem = "Alguns dados não estão no formato esperado."

    log.info("validação recusada: %s", problemas)
    return JSONResponse(
        status_code=422,
        content=ErroOut(codigo="DADOS_INVALIDOS", mensagem=mensagem).model_dump(),
    )


@app.exception_handler(ServicoIndisponivel)
async def tratar_servico_indisponivel(request: Request, erro: ServicoIndisponivel):
    """O serviço de autenticação não respondeu — não é culpa do token.

    Devolver 401 mandaria a pessoa fazer login, que também não funcionaria, e
    esconderia a indisponibilidade atrás de um erro de credencial.
    """
    log.error("serviço de autenticação indisponível: %s", erro)
    return JSONResponse(
        status_code=503,
        content=ErroOut(
            codigo="AUTENTICACAO_INDISPONIVEL",
            mensagem="Serviço de autenticação indisponível. "
            "Tente novamente em instantes.",
        ).model_dump(),
    )


@app.exception_handler(ErroDeAutenticacao)
async def tratar_erro_de_autenticacao(request: Request, erro: ErroDeAutenticacao):
    """Falha vinda do GoTrue. O status dele é preservado quando faz sentido.

    Um 5xx do serviço de autenticação vira 502: o problema é nosso dependente,
    não da requisição de quem chamou.
    """
    status = erro.status if 400 <= erro.status < 500 else 502
    return JSONResponse(
        status_code=status,
        content=ErroOut(
            codigo="FALHA_DE_AUTENTICACAO", mensagem=erro.mensagem
        ).model_dump(),
    )


@app.get("/health", tags=["infraestrutura"])
def health():
    """Sem autenticação — usado pelo healthcheck do Docker na Fase 5.

    Consulta o banco de propósito. Um health que só confirma que o processo
    subiu faria o container reportar `healthy` com o PostgreSQL fora, e o
    `depends_on: service_healthy` da F5 liberaria o frontend contra uma API que
    não funciona.
    """
    try:
        with conexao() as con:
            con.execute("select 1")
    except Exception as erro:  # noqa: BLE001 - qualquer falha aqui é indisponibilidade
        log.warning("health: banco indisponível: %s", erro)
        return JSONResponse(
            status_code=503, content={"status": "degradado", "banco": "indisponivel"}
        )
    return {"status": "ok", "banco": "ok"}


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


app.include_router(auth.router)
app.include_router(contas.router)
app.include_router(movimentacao.router)
app.include_router(extrato.router)

__all__ = ["app", "NaoAutenticado"]
