"""Limite de requisições (RNF-3.9).

Protege duas coisas diferentes, por motivos diferentes:

* **Login e cadastro** — contra força bruta. Sem limite, testar senhas é só uma
  questão de tempo, e a validação de credencial fica sendo a única barreira.
* **Movimentação** — contra engano e automação descontrolada. Trinta saques por
  minuto na mesma conta não é uso humano.

## Onde este limitador vive

Na memória do processo. Isso é honesto para o desenho atual — um container de
backend, como no `docker-compose.yml` — e **insuficiente para mais de uma
réplica**: cada processo contaria por si, e o limite efetivo seria multiplicado
pelo número delas.

Trocar por um contador compartilhado (Redis, ou a própria tabela do PostgreSQL)
é substituir `ContadorEmMemoria` por outra implementação de `Contador`. A
interface existe para que essa troca não toque em nenhuma rota.

## O cabeçalho `X-Forwarded-For`

Só é lido quando `CONFIAR_EM_PROXY=true`. Confiar nele por padrão seria pior que
não ter limite nenhum: qualquer um forjaria o cabeçalho a cada requisição e
teria uma chave nova toda vez, o que **desliga** a proteção enquanto aparenta
tê-la.
"""

import threading
import time
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from backend.config import Configuracao
from backend.core.erros import ErroDeDominio


class LimiteExcedido(ErroDeDominio):
    codigo = "LIMITE_EXCEDIDO"
    mensagem_padrao = "Muitas tentativas. Aguarde um pouco e tente de novo."

    def __init__(self, mensagem: str | None = None, esperar_segundos: int = 60):
        super().__init__(mensagem)
        self.esperar_segundos = esperar_segundos


@dataclass(frozen=True, slots=True)
class Regra:
    """Quantas requisições cabem numa janela, e de que tamanho é a janela."""

    quantidade: int
    janela_segundos: int

    @property
    def descricao(self) -> str:
        minutos = self.janela_segundos // 60
        unidade = f"{minutos} min" if minutos else f"{self.janela_segundos}s"
        return f"{self.quantidade} por {unidade}"


class Contador(Protocol):
    """O que um limitador precisa saber contar.

    Existe para que trocar memória por Redis não toque em rota nenhuma.
    """

    def registrar(self, chave: str, janela_segundos: int) -> tuple[int, int]:
        """Conta mais uma ocorrência. Devolve `(total, segundos_até_zerar)`."""
        ...


class ContadorEmMemoria:
    """Janela fixa, num dicionário protegido por lock.

    Janela fixa, e não deslizante: é mais simples e o efeito de borda — até o
    dobro do limite na virada — é aceitável para o que isto protege. Uma janela
    deslizante exigiria guardar cada horário, e o custo não se paga aqui.
    """

    def __init__(self) -> None:
        self._contagens: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self._ultima_limpeza = time.monotonic()

    def registrar(self, chave: str, janela_segundos: int) -> tuple[int, int]:
        agora = time.monotonic()
        with self._lock:
            self._limpar_expirados(agora)
            total, expira_em = self._contagens.get(chave, (0, 0.0))
            if agora >= expira_em:
                total, expira_em = 0, agora + janela_segundos
            total += 1
            self._contagens[chave] = (total, expira_em)
            return total, max(1, int(expira_em - agora))

    def _limpar_expirados(self, agora: float) -> None:
        """Sem isto, o dicionário cresce para sempre — cada IP novo deixa uma
        entrada que nunca sai, e um ataque distribuído viraria vazamento de
        memória em vez de bloqueio."""
        if agora - self._ultima_limpeza < 60:
            return
        self._ultima_limpeza = agora
        vencidas = [c for c, (_, exp) in self._contagens.items() if agora >= exp]
        for chave in vencidas:
            del self._contagens[chave]

    def zerar(self) -> None:
        """Usado pelos testes; nenhum caminho de produção chama."""
        with self._lock:
            self._contagens.clear()


class Limitador:
    def __init__(self, contador: Contador | None = None):
        self.contador = contador or ContadorEmMemoria()

    def exigir(self, chave: str, regra: Regra) -> None:
        total, esperar = self.contador.registrar(chave, regra.janela_segundos)
        if total > regra.quantidade:
            raise LimiteExcedido(
                f"Muitas tentativas ({regra.descricao}). "
                f"Aguarde {esperar}s e tente de novo.",
                esperar_segundos=esperar,
            )


#: Instância única do processo. Um limitador por processo é o ponto — contadores
#: separados por requisição não contariam nada.
limitador = Limitador()


def endereco_de(pedido: Request, cfg: Configuracao) -> str:
    """De onde veio a requisição, para servir de chave.

    `X-Forwarded-For` só entra quando o operador declarou que há um proxy à
    frente. Sem essa declaração, o cabeçalho é ignorado — aceitá-lo permitiria
    forjar uma origem nova a cada requisição e passar por baixo do limite.
    """
    if cfg.confiar_em_proxy:
        encaminhado = pedido.headers.get("X-Forwarded-For")
        if encaminhado:
            # o primeiro é o cliente original; os demais são os proxies
            return encaminhado.split(",")[0].strip()
    return pedido.client.host if pedido.client else "desconhecido"


# ---------------------------------------------------------------------------
# Regras aplicadas
# ---------------------------------------------------------------------------

#: Força bruta de senha precisa de muitas tentativas; seis a cada quinze minutos
#: torna o ataque inviável sem atrapalhar quem esqueceu a senha.
LOGIN_POR_ORIGEM = Regra(quantidade=6, janela_segundos=900)

#: Por e-mail também: sem isto, um atacante com muitos endereços de origem
#: atacaria uma conta específica sem nunca esbarrar no limite por origem.
LOGIN_POR_EMAIL = Regra(quantidade=6, janela_segundos=900)

#: Cadastro é mais caro que login — cria usuário no GoTrue — e não tem por que
#: acontecer em rajada.
REGISTRO_POR_ORIGEM = Regra(quantidade=10, janela_segundos=3600)

#: Trinta por minuto não atrapalha ninguém usando a interface, e corta
#: automação descontrolada.
MOVIMENTACAO_POR_TITULAR = Regra(quantidade=30, janela_segundos=60)


def limitar_login(pedido: Request, email: str, cfg: Configuracao) -> None:
    origem = endereco_de(pedido, cfg)
    limitador.exigir(f"login:origem:{origem}", LOGIN_POR_ORIGEM)
    limitador.exigir(f"login:email:{email.strip().lower()}", LOGIN_POR_EMAIL)


def limitar_registro(pedido: Request, cfg: Configuracao) -> None:
    limitador.exigir(f"registro:{endereco_de(pedido, cfg)}", REGISTRO_POR_ORIGEM)


def limitar_movimentacao(cliente_id: int) -> None:
    """Aplica o limite de movimentação a um titular.

    A chave é o titular, não a origem: duas pessoas atrás do mesmo NAT não
    deveriam competir pelo mesmo limite, e a mesma pessoa em duas redes não
    deveria contornar o dela.

    Recebe o id já resolvido em vez de revalidar o token: a rota tem o titular
    pela dependência de titularidade, e validar o JWT de novo seria trabalho
    repetido a cada requisição.
    """
    limitador.exigir(f"movimentacao:{cliente_id}", MOVIMENTACAO_POR_TITULAR)
