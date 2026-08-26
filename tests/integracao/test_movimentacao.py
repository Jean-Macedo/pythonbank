"""Funções de movimentação (RN-1.9 a RN-1.13).

Estes testes exercitam o SQL, não o Python. As mesmas regras já são testadas no
domínio; aqui o que se verifica é que o banco as impõe **também** quando alguém
passa por fora da aplicação.
"""

from decimal import Decimal

import psycopg
import pytest


def erro_de(excinfo) -> str:
    """Extrai o código estável levantado pela função PL/pgSQL."""
    return str(excinfo.value).splitlines()[0].strip()


class TestDeposito:
    def test_soma_ao_saldo(self, banco, abrir, saldo):
        conta = abrir(saldo="100.00")
        banco.execute("select realizar_deposito(%s, 50.25)", (conta,))
        assert saldo(conta) == Decimal("150.25")

    def test_registra_no_ledger(self, banco, abrir):
        conta = abrir()
        banco.execute("select realizar_deposito(%s, 50.00)", (conta,))
        lancamento = banco.execute(
            "select tipo, valor, saldo_apos from transacoes where conta_id = %s",
            (conta,),
        ).fetchone()
        assert lancamento == ("deposito", Decimal("50.00"), Decimal("50.00"))

    @pytest.mark.parametrize("valor", ["0", "-10.00"])
    def test_valor_nao_positivo_e_recusado(self, banco, abrir, valor):
        conta = abrir()
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select realizar_deposito(%s, %s)", (conta, valor))
        assert erro_de(e) == "VALOR_INVALIDO"

    def test_conta_inexistente(self, banco):
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select realizar_deposito(999999, 10.00)")
        assert erro_de(e) == "CONTA_NAO_ENCONTRADA"

    def test_conta_encerrada_e_indistinguivel_de_inexistente(self, banco, abrir):
        """RN-1.13 — quem chama não descobre que a conta existe mas está inativa."""
        conta = abrir()
        banco.execute("select encerrar_conta(%s)", (conta,))
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select realizar_deposito(%s, 10.00)", (conta,))
        assert erro_de(e) == "CONTA_NAO_ENCONTRADA"


class TestSaque:
    def test_subtrai_do_saldo(self, banco, abrir, saldo):
        conta = abrir(saldo="500.00")
        banco.execute("select realizar_saque(%s, 120.35)", (conta,))
        assert saldo(conta) == Decimal("379.65")

    def test_saldo_inteiro_e_permitido(self, banco, abrir, saldo):
        conta = abrir(saldo="500.00")
        banco.execute("select realizar_saque(%s, 500.00)", (conta,))
        assert saldo(conta) == Decimal("0.00")

    def test_um_centavo_acima_do_saldo_e_recusado(self, banco, abrir):
        conta = abrir(saldo="500.00")
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select realizar_saque(%s, 500.01)", (conta,))
        assert erro_de(e) == "SALDO_INSUFICIENTE"

    def test_recusa_nao_deixa_rastro_no_ledger(self, banco, abrir, saldo):
        """RN-1.10 — a verificação é a cláusula where: nada é escrito e desfeito."""
        conta = abrir(saldo="100.00")
        with pytest.raises(psycopg.errors.RaiseException):
            banco.execute("select realizar_saque(%s, 999.00)", (conta,))
        assert saldo(conta) == Decimal("100.00")
        n = banco.execute(
            "select count(*) from transacoes where conta_id = %s and tipo = 'saque'",
            (conta,),
        ).fetchone()[0]
        assert n == 0


class TestTransferencia:
    def test_move_valor_entre_contas(self, banco, abrir, saldo):
        origem = abrir(apelido="Origem", saldo="500.00")
        destino = abrir(tipo="poupanca", apelido="Destino")
        banco.execute("select transferir(%s, %s, 200.00)", (origem, destino))
        assert saldo(origem) == Decimal("300.00")
        assert saldo(destino) == Decimal("200.00")

    def test_registra_nas_duas_pontas_com_contraparte(self, banco, abrir):
        origem = abrir(apelido="Origem", saldo="500.00")
        destino = abrir(tipo="poupanca", apelido="Destino")
        banco.execute("select transferir(%s, %s, 200.00)", (origem, destino))

        linhas = dict(
            banco.execute(
                """
                select tipo, contraparte_id from transacoes
                 where tipo like 'transferencia%%' order by tipo
                """
            ).fetchall()
        )
        assert linhas["transferencia_saida"] == destino
        assert linhas["transferencia_entrada"] == origem

    def test_para_a_mesma_conta_e_recusada(self, banco, abrir):
        conta = abrir(saldo="100.00")
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select transferir(%s, %s, 10.00)", (conta, conta))
        assert erro_de(e) == "CONTAS_IGUAIS"

    def test_sem_saldo_nao_altera_nenhuma_das_duas(self, banco, abrir, saldo):
        origem = abrir(apelido="Origem", saldo="50.00")
        destino = abrir(tipo="poupanca", apelido="Destino")
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select transferir(%s, %s, 100.00)", (origem, destino))
        assert erro_de(e) == "SALDO_INSUFICIENTE"
        assert saldo(origem) == Decimal("50.00")
        assert saldo(destino) == Decimal("0.00")

    def test_destino_encerrado_desfaz_o_debito(self, banco, abrir, saldo):
        """A transação inteira reverte: a origem não pode ficar debitada."""
        origem = abrir(apelido="Origem", saldo="500.00")
        destino = abrir(tipo="poupanca", apelido="Destino")
        banco.execute("select encerrar_conta(%s)", (destino,))
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select transferir(%s, %s, 100.00)", (origem, destino))
        assert erro_de(e) == "CONTA_NAO_ENCONTRADA"
        assert saldo(origem) == Decimal("500.00")


class TestCicloDeVidaDaConta:
    def test_numero_gerado_pelo_banco_e_sequencial(self, banco, abrir):
        """RN-1.8 — quem numera é a sequence, não a aplicação."""
        a, b = abrir(apelido="A"), abrir(apelido="B")
        numeros = [
            banco.execute("select numero from contas where id = %s", (c,)).fetchone()[0]
            for c in (a, b)
        ]
        assert numeros[0] != numeros[1]
        assert all(n.isdigit() and len(n) == 8 for n in numeros)

    def test_apelido_duplicado_no_mesmo_cliente(self, banco, abrir):
        abrir(apelido="Reserva")
        with pytest.raises(psycopg.errors.RaiseException) as e:
            abrir(tipo="poupanca", apelido="Reserva")
        assert erro_de(e) == "APELIDO_DUPLICADO"

    def test_apelido_duplicado_ignora_caixa(self, banco, abrir):
        abrir(apelido="Reserva")
        with pytest.raises(psycopg.errors.RaiseException):
            abrir(tipo="poupanca", apelido="reserva")

    def test_varias_contas_sem_apelido_sao_permitidas(self, banco, abrir):
        abrir()
        abrir(tipo="poupanca")

    def test_encerrar_exige_saldo_zero(self, banco, abrir):
        conta = abrir(saldo="10.00")
        with pytest.raises(psycopg.errors.RaiseException) as e:
            banco.execute("select encerrar_conta(%s)", (conta,))
        assert erro_de(e) == "CONTA_NAO_ENCERRAVEL"

    def test_encerrar_desativa_mas_preserva_o_historico(self, banco, abrir):
        conta = abrir(saldo="10.00")
        banco.execute("select realizar_saque(%s, 10.00)", (conta,))
        banco.execute("select encerrar_conta(%s)", (conta,))

        ativa = banco.execute(
            "select ativa from contas where id = %s", (conta,)
        ).fetchone()[0]
        n = banco.execute(
            "select count(*) from transacoes where conta_id = %s", (conta,)
        ).fetchone()[0]
        assert ativa is False
        assert n == 2


class TestConstraintsDoSchema:
    def test_saldo_negativo_e_recusado_pela_constraint(self, banco, abrir):
        """Mesmo por fora das funções, o banco não aceita saldo negativo."""
        conta = abrir()
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.execute("update contas set saldo = -1 where id = %s", (conta,))

    def test_cpf_fora_do_formato_e_recusado(self, banco):
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.execute(
                """
                insert into clientes (auth_user_id, nome, cpf, email, telefone,
                                      data_nascimento)
                values (gen_random_uuid(), 'X', 'abc', 'x@x.com', '11999999999',
                        '2000-01-01')
                """
            )

    def test_cpf_duplicado_e_recusado(self, banco):
        with pytest.raises(psycopg.errors.UniqueViolation):
            banco.execute(
                """
                insert into clientes (auth_user_id, nome, cpf, email, telefone,
                                      data_nascimento)
                values (gen_random_uuid(), 'X', '52998224725', 'x@x.com',
                        '11999999999', '2000-01-01')
                """
            )

    def test_transferencia_orfa_e_recusada(self, banco, abrir):
        """A constraint contraparte_coerente impede lançamento incoerente."""
        conta = abrir()
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.execute(
                """
                insert into transacoes (conta_id, tipo, valor, saldo_apos)
                values (%s, 'transferencia_saida', 10, 0)
                """,
                (conta,),
            )

    def test_deposito_com_contraparte_e_recusado(self, banco, abrir):
        conta = abrir()
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.execute(
                """
                insert into transacoes (conta_id, tipo, valor, saldo_apos, contraparte_id)
                values (%s, 'deposito', 10, 10, %s)
                """,
                (conta, conta),
            )
