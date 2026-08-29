"""Tradução entre domínio e persistência (DT-05).

Este é o único módulo que fala SQL. As rotas não montam query, e o domínio não
sabe que existe banco.

Toda movimentação passa pelas funções PL/pgSQL da Fase 1 (RN-2.6): nada de
`update` direto em `contas` nem `insert` direto em `transacoes` daqui.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import psycopg

from backend.core.erros import ContaNaoEncontrada, ErroDeDominio, por_codigo
from backend.infra.database import conexao

# ---------------------------------------------------------------------------
# Modelos de leitura
#
# Não são objetos de domínio: `core.Conta` guarda saldo e histórico em memória,
# e a partir da Fase 1 quem guarda isso é o banco. Aqui trafega só o que foi
# lido, sem comportamento.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClienteLido:
    id: int
    auth_user_id: str
    nome: str
    cpf: str
    email: str
    telefone: str
    data_nascimento: date


@dataclass(frozen=True, slots=True)
class ContaLida:
    id: int
    cliente_id: int
    agencia: str
    numero: str
    tipo: str
    apelido: str | None
    saldo: Decimal
    ativa: bool


@dataclass(frozen=True, slots=True)
class LancamentoLido:
    id: int
    tipo: str
    valor: Decimal
    saldo_apos: Decimal
    contraparte: str | None
    data_hora: datetime


def traduzir_erro(erro: psycopg.errors.RaiseException) -> ErroDeDominio:
    """Converte a exceção do PL/pgSQL no erro de domínio correspondente.

    As funções da Fase 1 levantam códigos estáveis justamente para que esta
    tradução não precise interpretar mensagem em português.
    """
    codigo = str(erro).splitlines()[0].strip()
    return por_codigo(codigo)


class ClienteRepo:
    def buscar_por_auth_id(self, auth_user_id: str) -> ClienteLido | None:
        with conexao() as con:
            linha = con.execute(
                """
                select id, auth_user_id, nome, cpf, email, telefone, data_nascimento
                  from clientes where auth_user_id = %s
                """,
                (auth_user_id,),
            ).fetchone()
        return ClienteLido(*linha) if linha else None

    def buscar_por_id(self, cliente_id: int) -> ClienteLido | None:
        with conexao() as con:
            linha = con.execute(
                """
                select id, auth_user_id, nome, cpf, email, telefone, data_nascimento
                  from clientes where id = %s
                """,
                (cliente_id,),
            ).fetchone()
        return ClienteLido(*linha) if linha else None


CAMPOS_CONTA = "id, cliente_id, agencia, numero, tipo, apelido, saldo, ativa"


class ContaRepo:
    # ---------------------------------------------------------------- leitura

    def listar_do_cliente(self, cliente_id: int) -> list[ContaLida]:
        with conexao() as con:
            linhas = con.execute(
                f"select {CAMPOS_CONTA} from contas "
                "where cliente_id = %s and ativa order by id",
                (cliente_id,),
            ).fetchall()
        return [ContaLida(*linha) for linha in linhas]

    def buscar(self, conta_id: int) -> ContaLida | None:
        with conexao() as con:
            linha = con.execute(
                f"select {CAMPOS_CONTA} from contas where id = %s", (conta_id,)
            ).fetchone()
        return ContaLida(*linha) if linha else None

    def buscar_por_agencia_numero(self, agencia: str, numero: str) -> ContaLida | None:
        with conexao() as con:
            linha = con.execute(
                f"select {CAMPOS_CONTA} from contas "
                "where agencia = %s and numero = %s and ativa",
                (agencia, numero),
            ).fetchone()
        return ContaLida(*linha) if linha else None

    def contar_ativas(self, cliente_id: int) -> int:
        with conexao() as con:
            return con.execute(
                "select count(*) from contas where cliente_id = %s and ativa",
                (cliente_id,),
            ).fetchone()[0]

    def apelidos_do_cliente(self, cliente_id: int) -> list[str]:
        with conexao() as con:
            linhas = con.execute(
                "select apelido from contas "
                "where cliente_id = %s and ativa and apelido is not null",
                (cliente_id,),
            ).fetchall()
        return [linha[0] for linha in linhas]

    # ------------------------------------------------------------ ciclo de vida

    def abrir(self, cliente_id: int, tipo: str, apelido: str | None) -> ContaLida:
        with conexao() as con:
            try:
                conta_id = con.execute(
                    "select (abrir_conta(%s, %s, %s)).id", (cliente_id, tipo, apelido)
                ).fetchone()[0]
            except psycopg.errors.RaiseException as erro:
                raise traduzir_erro(erro) from erro
        return self.buscar(conta_id)

    def renomear(self, conta_id: int, apelido: str | None) -> ContaLida:
        with conexao() as con:
            try:
                con.execute(
                    "update contas set apelido = %s where id = %s and ativa",
                    (apelido, conta_id),
                )
            except psycopg.errors.UniqueViolation as erro:
                raise por_codigo("APELIDO_DUPLICADO") from erro
        return self.buscar(conta_id)

    def encerrar(self, conta_id: int) -> None:
        with conexao() as con:
            try:
                con.execute("select encerrar_conta(%s)", (conta_id,))
            except psycopg.errors.RaiseException as erro:
                raise traduzir_erro(erro) from erro

    # ------------------------------------------------------------ movimentação

    def _movimentar(self, funcao: str, *args) -> Decimal:
        marcadores = ", ".join(["%s"] * len(args))
        with conexao() as con:
            try:
                return con.execute(
                    f"select {funcao}({marcadores})", args
                ).fetchone()[0]
            except psycopg.errors.RaiseException as erro:
                raise traduzir_erro(erro) from erro

    def depositar(self, conta_id: int, valor: Decimal) -> Decimal:
        return self._movimentar("realizar_deposito", conta_id, valor)

    def sacar(self, conta_id: int, valor: Decimal) -> Decimal:
        return self._movimentar("realizar_saque", conta_id, valor)

    def transferir(self, origem_id: int, destino_id: int, valor: Decimal) -> Decimal:
        return self._movimentar("transferir", origem_id, destino_id, valor)

    def ultimo_lancamento(self, conta_id: int) -> int:
        with conexao() as con:
            return con.execute(
                "select id from transacoes where conta_id = %s "
                "order by id desc limit 1",
                (conta_id,),
            ).fetchone()[0]

    # ----------------------------------------------------------------- extrato

    def extrato(
        self, conta_id: int, limite: int, cursor: tuple[datetime, int] | None = None
    ) -> list[LancamentoLido]:
        """Página do extrato, mais recente primeiro.

        Cursor sobre `(data_hora, id)` em vez de `offset` (RF-2.8): o ledger
        recebe inserções durante a navegação, e `offset` faria lançamentos
        pularem ou repetirem entre páginas.
        """
        # colunas qualificadas: o join com `contas` traz outro `id` e outro
        # `data_hora` para o escopo, e sem o prefixo a referência é ambígua
        condicao, parametros = "t.conta_id = %s", [conta_id]
        if cursor is not None:
            condicao += " and (t.data_hora, t.id) < (%s, %s)"
            parametros.extend(cursor)
        parametros.append(limite)

        with conexao() as con:
            linhas = con.execute(
                f"""
                select t.id, t.tipo, t.valor, t.saldo_apos,
                       cp.agencia || '/' || cp.numero as contraparte, t.data_hora
                  from transacoes t
                  left join contas cp on cp.id = t.contraparte_id
                 where {condicao}
                 order by t.data_hora desc, t.id desc
                 limit %s
                """,
                parametros,
            ).fetchall()
        return [LancamentoLido(*linha) for linha in linhas]


def exigir_conta(conta: ContaLida | None) -> ContaLida:
    if conta is None or not conta.ativa:
        raise ContaNaoEncontrada()
    return conta
