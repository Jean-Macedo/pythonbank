"""CLI do Banco Jean.

Camada de apresentação: lê do terminal, delega ao domínio, formata a resposta.
Não valida nada por conta própria — se uma regra estiver aqui, está no lugar
errado. Enquanto este arquivo roda sobre `core/` sem importar infraestrutura, a
separação de DT-05 está comprovada na prática.

Este CLI é descartado na Fase 4, quando o React assume a apresentação.
"""

import sys

from backend.core import dinheiro
from backend.core.cliente import Cliente
from backend.core.conta import TipoConta
from backend.core.erros import ErroDeDominio
from backend.core.eventos import TipoTransacao

LARGURA = 46

ROTULO_TRANSACAO = {
    TipoTransacao.DEPOSITO: "Depósito",
    TipoTransacao.SAQUE: "Saque",
    TipoTransacao.TRANSFERENCIA_SAIDA: "Transferência enviada",
    TipoTransacao.TRANSFERENCIA_ENTRADA: "Transferência recebida",
}


class Sessao:
    """Estado da sessão: quem está logado e sobre qual conta opera."""

    def __init__(self):
        self.cliente: Cliente | None = None
        self.conta_ativa = None

    @property
    def autenticado(self) -> bool:
        return self.cliente is not None

    def exigir_cliente(self) -> Cliente:
        if self.cliente is None:
            raise ErroDeDominio("Cadastre um cliente antes de continuar.")
        return self.cliente

    def exigir_conta(self):
        self.exigir_cliente()
        if self.conta_ativa is None or not self.conta_ativa.ativa:
            raise ErroDeDominio("Selecione uma conta antes de continuar.")
        return self.conta_ativa


# ---------------------------------------------------------------------------
# Entrada e saída
# ---------------------------------------------------------------------------


def titulo(texto: str) -> None:
    print("\n" + "=" * LARGURA)
    print(texto.center(LARGURA))
    print("=" * LARGURA)


def perguntar(rotulo: str) -> str:
    return input(f"{rotulo}: ").strip()


def escolher_conta(cliente: Cliente, pergunta="Escolha a conta"):
    contas = cliente.contas
    if not contas:
        raise ErroDeDominio("Você ainda não tem contas abertas.")

    for indice, conta in enumerate(contas, start=1):
        print(f"  {indice} - {conta.rotulo}  {dinheiro.formatar(conta.saldo)}")

    escolha = perguntar(pergunta)
    if not escolha.isdigit() or not 1 <= int(escolha) <= len(contas):
        raise ErroDeDominio("Opção de conta inválida.")
    return contas[int(escolha) - 1]


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------


def cadastrar_cliente(sessao: Sessao) -> None:
    titulo("CADASTRO")
    sessao.cliente = Cliente(
        nome=perguntar("Nome completo"),
        data_nascimento=perguntar("Data de nascimento (DD/MM/AAAA)"),
        cpf=perguntar("CPF"),
        email=perguntar("E-mail"),
        telefone=perguntar("Telefone com DDD (apenas números)"),
    )
    sessao.conta_ativa = sessao.cliente.abrir_conta(TipoConta.CORRENTE, "Principal")
    print(f"\nCadastro concluído. {sessao.cliente.nome}, {sessao.cliente.idade} anos.")
    print(f"Conta corrente aberta: {sessao.conta_ativa.identificacao}")


def abrir_conta(sessao: Sessao) -> None:
    cliente = sessao.exigir_cliente()
    titulo("ABRIR CONTA")
    print("Tipos disponíveis: " + ", ".join(t.value for t in TipoConta))

    conta = cliente.abrir_conta(
        tipo=perguntar("Tipo"),
        apelido=perguntar("Apelido (opcional)"),
    )
    sessao.conta_ativa = conta
    print(f"\nConta aberta: {conta.rotulo}")
    print(f"Você tem {len(cliente.contas)} de {Cliente.LIMITE_DE_CONTAS} contas.")


def selecionar_conta(sessao: Sessao) -> None:
    cliente = sessao.exigir_cliente()
    titulo("SUAS CONTAS")
    sessao.conta_ativa = escolher_conta(cliente)
    print(f"\nConta ativa: {sessao.conta_ativa.rotulo}")


def depositar(sessao: Sessao) -> None:
    conta = sessao.exigir_conta()
    transacao = conta.depositar(perguntar("Valor do depósito"))
    print(f"\nDepósito de {dinheiro.formatar(transacao.valor)} efetuado.")
    print(f"Saldo: {dinheiro.formatar(transacao.saldo_apos)}")


def sacar(sessao: Sessao) -> None:
    conta = sessao.exigir_conta()
    transacao = conta.sacar(perguntar("Valor do saque"))
    print(f"\nSaque de {dinheiro.formatar(transacao.valor)} efetuado.")
    print(f"Saldo: {dinheiro.formatar(transacao.saldo_apos)}")


def transferir(sessao: Sessao) -> None:
    cliente = sessao.exigir_cliente()
    origem = sessao.exigir_conta()
    titulo("TRANSFERÊNCIA")
    print(f"Origem: {origem.rotulo}\n")
    print("Destino:")

    destino = escolher_conta(cliente, "Escolha a conta de destino")
    saida, _ = origem.transferir_para(destino, perguntar("Valor"))

    print(f"\n{dinheiro.formatar(saida.valor)} transferidos para {destino.rotulo}.")
    print(f"Saldo em {origem.rotulo}: {dinheiro.formatar(saida.saldo_apos)}")


def ver_extrato(sessao: Sessao) -> None:
    conta = sessao.exigir_conta()
    titulo("EXTRATO")
    print(f"Titular: {conta.titular.nome}")
    print(f"CPF:     {conta.titular.cpf_formatado}")
    print(f"Conta:   {conta.rotulo}")
    print("-" * LARGURA)

    if not conta.historico:
        print("Nenhuma movimentação registrada.")
    else:
        for transacao in conta.historico:
            data = transacao.data_hora.strftime("%d/%m/%Y %H:%M")
            sinal = "+" if transacao.tipo.e_entrada else "-"
            rotulo = ROTULO_TRANSACAO[transacao.tipo]
            print(f"{data}  {rotulo:<24} {sinal}{dinheiro.formatar(transacao.valor)}")

    print("-" * LARGURA)
    print(f"{'Saldo atual':<28} {dinheiro.formatar(conta.saldo):>16}")


def encerrar_conta(sessao: Sessao) -> None:
    cliente = sessao.exigir_cliente()
    titulo("ENCERRAR CONTA")
    conta = escolher_conta(cliente, "Escolha a conta a encerrar")

    cliente.encerrar_conta(conta)
    if sessao.conta_ativa is conta:
        sessao.conta_ativa = cliente.contas[0] if cliente.contas else None
    print(f"\nConta {conta.identificacao} encerrada.")


def ver_patrimonio(sessao: Sessao) -> None:
    cliente = sessao.exigir_cliente()
    titulo("RESUMO")
    for conta in cliente.contas:
        print(f"  {conta.rotulo:<32} {dinheiro.formatar(conta.saldo):>12}")
    print("-" * LARGURA)
    print(f"  {'Total':<32} {dinheiro.formatar(cliente.patrimonio):>12}")


# ---------------------------------------------------------------------------
# Laço principal
# ---------------------------------------------------------------------------

ACOES = {
    1: ("Cadastrar cliente", cadastrar_cliente),
    2: ("Abrir nova conta", abrir_conta),
    3: ("Selecionar conta", selecionar_conta),
    4: ("Depositar", depositar),
    5: ("Sacar", sacar),
    6: ("Transferir", transferir),
    7: ("Ver extrato", ver_extrato),
    8: ("Ver resumo das contas", ver_patrimonio),
    9: ("Encerrar uma conta", encerrar_conta),
}


def mostrar_menu(sessao: Sessao) -> None:
    titulo("BANCO JEAN")
    if sessao.conta_ativa:
        print(f"Conta ativa: {sessao.conta_ativa.rotulo}")
        print(f"Saldo:       {dinheiro.formatar(sessao.conta_ativa.saldo)}\n")
    elif sessao.autenticado:
        print("Nenhuma conta selecionada.\n")
    else:
        print("Nenhum cliente cadastrado.\n")

    for opcao, (rotulo, _) in ACOES.items():
        print(f"{opcao} - {rotulo}")
    print("0 - Sair")


def ler_opcao() -> int | None:
    """Devolve None quando a entrada não é uma opção numérica (RF-0.5)."""
    try:
        return int(input("\nEscolha uma opção: ").strip())
    except ValueError:
        return None


def main() -> int:
    sessao = Sessao()

    while True:
        mostrar_menu(sessao)

        try:
            opcao = ler_opcao()
        except (EOFError, KeyboardInterrupt):
            print("\nSessão interrompida.")
            return 0

        if opcao == 0:
            nome = sessao.cliente.nome if sessao.cliente else None
            print(f"\nAté logo{', ' + nome if nome else ''}!")
            return 0

        acao = ACOES.get(opcao) if opcao is not None else None
        if acao is None:
            print("\nOpção inválida. Escolha um número da lista.")
            continue

        # Um único ponto de tratamento: nenhuma ação decide o que fazer com erro
        # de domínio, e nenhuma mensagem de sucesso pode ser impressa em caminho
        # de falha (RF-0.4).
        try:
            acao[1](sessao)
        except ErroDeDominio as erro:
            print(f"\n[{erro.codigo}] {erro.mensagem}")
        except (EOFError, KeyboardInterrupt):
            print("\nOperação cancelada.")


if __name__ == "__main__":
    sys.exit(main())
