"""A CLI é apresentação: interpreta o que a pessoa digita e delega o resto.

Estes testes cobrem a conversão de entrada. Encontrada faltando ao verificar o
passo a passo do README num clone limpo: a interface web aceitava `1.234,56` e a
CLI recusava `100,00` — o programa, em português, exigindo o separador da
máquina de quem escreve dinheiro com vírgula.
"""

import pytest

from interface import perguntar_valor


def digitando(texto, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: texto)
    return perguntar_valor("Valor")


class TestFormatoBrasileiro:
    @pytest.mark.parametrize(
        ("digitado", "esperado"),
        [
            ("100,00", "100.00"),
            ("1.234,56", "1234.56"),
            ("1.000.000,00", "1000000.00"),
            ("0,07", "0.07"),
        ],
    )
    def test_virgula_decimal_e_ponto_de_milhar(self, digitado, esperado, monkeypatch):
        assert digitando(digitado, monkeypatch) == esperado


class TestFormatoDaMaquina:
    @pytest.mark.parametrize(
        ("digitado", "esperado"),
        [("100.00", "100.00"), ("1234.56", "1234.56"), ("42", "42")],
    )
    def test_continua_valendo(self, digitado, esperado, monkeypatch):
        assert digitando(digitado, monkeypatch) == esperado

    def test_espacos_sao_ignorados(self, monkeypatch):
        assert digitando(" 1.234,56 ", monkeypatch) == "1234.56"


class TestOQueNaoDaParaEntender:
    """Segue para o domínio, que recusa com código próprio.

    A apresentação não valida — ela normaliza. Quem decide se o valor presta é
    `dinheiro.validar_positivo`, e é dele que sai a mensagem.
    """

    @pytest.mark.parametrize("digitado", ["abc", "", "R$ 10"])
    def test_o_dominio_recusa(self, digitado, monkeypatch):
        from backend.core.dinheiro import validar_positivo
        from backend.core.erros import ValorInvalido

        with pytest.raises(ValorInvalido):
            validar_positivo(digitando(digitado, monkeypatch))
