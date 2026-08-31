"""Cadastro, entrada e renovação de sessão.

Estas rotas ficam **fora** de `/api` porque são as únicas que não exigem token —
é onde o token nasce.

O backend não guarda senha: quem faz isso é o GoTrue. O que este módulo faz é
coordenar a criação do usuário lá com a do titular aqui, e garantir que não sobre
metade quando algo falha no meio.
"""

import logging

from fastapi import APIRouter, Depends, status

from backend.api.deps import get_cliente_repo
from backend.core.cliente import Cliente
from backend.core.erros import ErroDeDominio
from backend.infra import autenticacao
from backend.infra.autenticacao import Credencial, ErroDeAutenticacao
from backend.infra.repositorios import ClienteRepo
from backend.schemas import LoginIn, RefreshIn, RegistroIn, RegistroOut, SessaoOut

log = logging.getLogger("banco.auth")

router = APIRouter(prefix="/auth", tags=["autenticação"])


class EmailJaCadastrado(ErroDeDominio):
    codigo = "EMAIL_JA_CADASTRADO"
    mensagem_padrao = "Já existe um cadastro com este e-mail."


def para_sessao(credencial: Credencial) -> SessaoOut:
    return SessaoOut(
        access_token=credencial.access_token,
        refresh_token=credencial.refresh_token,
        expira_em=credencial.expira_em,
    )


@router.post("/registro", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
def registrar(entrada: RegistroIn, repo: ClienteRepo = Depends(get_cliente_repo)):
    """Cria usuário, titular e conta inicial.

    A ordem importa. Primeiro o domínio valida — CPF por dígito verificador,
    e-mail, telefone, data de nascimento — porque rejeitar antes de criar
    qualquer coisa evita ter o que desfazer. Só então o usuário é criado no
    GoTrue, e por último o titular e a conta, juntos numa transação.

    Se a etapa do banco falhar, o usuário do GoTrue é removido. Sem isso,
    sobraria um login que existe e não leva a lugar nenhum, e uma segunda
    tentativa com o mesmo e-mail bateria em "já cadastrado" para sempre.
    """
    # `Cliente` valida e normaliza; nada é criado se algo aqui levantar
    titular = Cliente(
        nome=entrada.nome,
        data_nascimento=entrada.data_nascimento,
        cpf=entrada.cpf,
        email=entrada.email,
        telefone=entrada.telefone,
    )

    try:
        auth_user_id, credencial = autenticacao.criar_usuario(
            titular.email, entrada.senha
        )
    except ErroDeAutenticacao as erro:
        # decidido pelo `error_code` do GoTrue, que é campo estruturado; a
        # mensagem é texto em inglês que muda entre versões
        if erro.codigo_gotrue in ("user_already_exists", "email_exists"):
            raise EmailJaCadastrado() from erro
        raise

    try:
        cliente, conta_id = repo.criar_com_conta_inicial(
            auth_user_id=auth_user_id,
            nome=titular.nome,
            cpf=titular.cpf,
            email=titular.email,
            telefone=titular.telefone,
            data_nascimento=titular.data_nascimento,
        )
    except Exception:
        # compensação: o usuário do GoTrue não pode sobreviver a um cadastro
        # que não chegou a criar o titular
        log.warning("cadastro falhou após criar %s; removendo usuário", auth_user_id)
        try:
            autenticacao.remover_usuario(auth_user_id)
        except Exception:  # noqa: BLE001 - a falha original é a que importa
            log.exception("não foi possível remover o usuário órfão %s", auth_user_id)
        raise

    return RegistroOut(
        cliente_id=cliente.id,
        conta_id=conta_id,
        sessao=para_sessao(credencial) if credencial else None,
    )


@router.post("/login", response_model=SessaoOut)
def login(entrada: LoginIn):
    return para_sessao(autenticacao.autenticar(entrada.email, entrada.senha))


@router.post("/refresh", response_model=SessaoOut)
def refresh(entrada: RefreshIn):
    """Renova o acesso sem pedir senha de novo (RF-3.4)."""
    return para_sessao(autenticacao.renovar(entrada.refresh_token))
