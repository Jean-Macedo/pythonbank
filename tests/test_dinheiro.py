from decimal import Decimal

import pytest

from core import dinheiro
from core.erros import ValorInvalido


class TestPrecisao:
    """RNF-0.15 — os testes que falham se alguém reintroduzir float (DT-01)."""

    def test_somar_dez_centavos_tres_vezes_da_trinta_exatos(self):
        total = dinheiro.ZERO
        for _ in range(3):
            total += dinheiro.para_decimal("0.10")
        assert total == Decimal("0.30")

    def test_float_equivalente_nao_daria_o_mesmo_resultado(self):
        """Documenta por que a regra existe: 0.1 * 3 != 0.3 em ponto flutuante."""
        assert 0.1 + 0.1 + 0.1 != 0.3

    def test_acumular_centavos_mil_vezes_nao_desvia(self):
        total = sum((dinheiro.para_decimal("0.01") for _ in range(1000)), dinheiro.ZERO)
        assert total == Decimal("10.00")


class TestParaDecimal:
    def test_aceita_string(self):
        assert dinheiro.para_decimal("12.34") == Decimal("12.34")

    def test_aceita_int(self):
        assert dinheiro.para_decimal(50) == Decimal("50.00")

    def test_aceita_decimal(self):
        assert dinheiro.para_decimal(Decimal("7.5")) == Decimal("7.50")

    def test_rejeita_float_com_type_error(self):
        """Float é erro de programação, não de domínio — falha alto e cedo."""
        with pytest.raises(TypeError, match="DT-01"):
            dinheiro.para_decimal(10.5)

    def test_rejeita_bool(self):
        with pytest.raises(TypeError):
            dinheiro.para_decimal(True)

    def test_rejeita_texto_nao_numerico(self):
        with pytest.raises(ValorInvalido):
            dinheiro.para_decimal("dez reais")

    def test_rejeita_nan(self):
        with pytest.raises(ValorInvalido):
            dinheiro.para_decimal("NaN")

    def test_rejeita_infinito(self):
        with pytest.raises(ValorInvalido):
            dinheiro.para_decimal("Infinity")


class TestQuantizacao:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("1.005", "1.01"),  # meio-para-cima, não meio-para-par
            ("1.004", "1.00"),
            ("2.675", "2.68"),
            ("0.999", "1.00"),
        ],
    )
    def test_arredonda_meio_para_cima(self, entrada, esperado):
        assert dinheiro.para_decimal(entrada) == Decimal(esperado)


class TestValidarPositivo:
    def test_aceita_valor_positivo(self):
        assert dinheiro.validar_positivo("0.01") == Decimal("0.01")

    def test_rejeita_zero(self):
        with pytest.raises(ValorInvalido):
            dinheiro.validar_positivo("0")

    def test_rejeita_negativo(self):
        with pytest.raises(ValorInvalido):
            dinheiro.validar_positivo("-5.00")

    def test_rejeita_valor_que_arredonda_para_zero(self):
        """Meio centavo não é dinheiro: vira 0,00 e deixa de ser positivo."""
        with pytest.raises(ValorInvalido):
            dinheiro.validar_positivo("0.004")


class TestFormatacao:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            ("0", "R$ 0,00"),
            ("1234.5", "R$ 1.234,50"),
            ("1000000", "R$ 1.000.000,00"),
            ("0.07", "R$ 0,07"),
        ],
    )
    def test_formata_no_padrao_brasileiro(self, valor, esperado):
        assert dinheiro.formatar(Decimal(valor)) == esperado
