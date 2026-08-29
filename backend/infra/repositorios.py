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
from psycopg.rows import class_row

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
class Movimentacao:
    """Resultado de uma movimentação: os dois valores vêm da mesma transação."""

    saldo: Decimal
    transacao_id: int


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
            return con.cursor(row_factory=class_row(ClienteLido)).execute(
                f"select {CAMPOS_CLIENTE} from clientes where auth_user_id = %s",
                (auth_user_id,),
            ).fetchone()

    def buscar_por_id(self, cliente_id: int) -> ClienteLido | None:
        with conexao() as con:
            return con.cursor(row_factory=class_row(ClienteLido)).execute(
                f"select {CAMPOS_CLIENTE} from clientes where id = %s", (cliente_id,)
            ).fetchone()


# Colunas nomeadas explicitamente e mapeadas por nome via `class_row`. Antes era
# `ContaLida(*linha)`, posicional: reordenar um campo da dataclass trocaria
# `saldo` por `ativa` sem erro nenhum, só dados corrompidos.
CAMPOS_CONTA = "id, cliente_id, agencia, numero, tipo, apelido, saldo, ativa"
CAMPOS_CLIENTE = "id, auth_user_id, nome, cpf, email, telefone, data_nascimento"


class ContaRepo:
    # ---------------------------------------------------------------- leitura

    def listar_do_cliente(self, cliente_id: int) -> list[ContaLida]:
        with conexao() as con:
            return con.cursor(row_factory=class_row(ContaLida)).execute(
                f"select {CAMPOS_CONTA} from contas "
                "where cliente_id = %s and ativa order by id",
                (cliente_id,),
            ).fetchall()

    def buscar(self, conta_id: int) -> ContaLida | None:
        with conexao() as con:
            return con.cursor(row_factory=class_row(ContaLida)).execute(
                f"select {CAMPOS_CONTA} from contas where id = %s", (conta_id,)
            ).fetchone()

    def buscar_por_agencia_numero(self, agencia: str, numero: str) -> ContaLida | None:
        with conexao() as con:
            return con.cursor(row_factory=class_row(ContaLida)).execute(
                f"select {CAMPOS_CONTA} from contas "
                "where agencia = %s and numero = %s and ativa",
                (agencia, numero),
            ).fetchone()

    # `contar_ativas` e `apelidos_do_cliente` foram removidos junto com as
    # corridas que habilitavam: ler a contagem ou a lista de apelidos para
    # decidir em Python é check-then-act. Quem decide agora é o banco, dentro da
    # mesma transação do insert.

    # ------------------------------------------------------------ ciclo de vida

    def abrir(
        self,
        cliente_id: int,
        tipo: str,
        apelido: str | None,
        limite_contas: int | None = None,
    ) -> ContaLida:
        """Abre a conta com o limite aplicado dentro da própria transação.

        O `limite_contas` vem do domínio (DT-05: a política é do Python), mas
        quem o aplica é o banco, sob lock da linha do cliente. Contar em Python
        e inserir depois era check-then-act: medido, 10 aberturas simultâneas
        furaram um limite de 5 e produziram 14 contas.
        """
        with conexao() as con:
            try:
                conta_id = con.execute(
                    "select (abrir_conta(%s, %s, %s, %s)).id",
                    (cliente_id, tipo, apelido, limite_contas),
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

    def _movimentar(self, funcao: str, *args) -> Movimentacao:
        """Devolve saldo e id do lançamento vindos da **mesma** chamada.

        Buscar o id depois, com um "último lançamento da conta", era uma corrida:
        entre a escrita e a busca, outra requisição insere a dela e o cliente
        recebe o comprovante errado. Medido antes da correção: 20 depósitos
        simultâneos devolveram 3 ids distintos para 20 lançamentos reais.
        """
        marcadores = ", ".join(["%s"] * len(args))
        with conexao() as con:
            try:
                saldo, transacao_id = con.execute(
                    f"select saldo, transacao_id from {funcao}({marcadores})", args
                ).fetchone()
            except psycopg.errors.RaiseException as erro:
                raise traduzir_erro(erro) from erro
        return Movimentacao(saldo=saldo, transacao_id=transacao_id)

    def depositar(self, conta_id: int, valor: Decimal) -> Movimentacao:
        return self._movimentar("realizar_deposito", conta_id, valor)

    def sacar(self, conta_id: int, valor: Decimal) -> Movimentacao:
        return self._movimentar("realizar_saque", conta_id, valor)

    def transferir(
        self, origem_id: int, destino_id: int, valor: Decimal
    ) -> Movimentacao:
        return self._movimentar("transferir", origem_id, destino_id, valor)

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
            return con.cursor(row_factory=class_row(LancamentoLido)).execute(
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


def exigir_conta(conta: ContaLida | None) -> ContaLida:
    if conta is None or not conta.ativa:
        raise ContaNaoEncontrada()
    return conta
