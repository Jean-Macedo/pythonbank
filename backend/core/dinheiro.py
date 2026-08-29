"""Representação monetária do domínio (DT-01).

Dinheiro é `Decimal` com duas casas, sempre. `float` é rejeitado na entrada em
vez de convertido: aceitar `0.1` silenciosamente reintroduz exatamente o erro
que este módulo existe para evitar.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from backend.core.erros import ValorInvalido

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")


def para_decimal(valor: str | int | Decimal) -> Decimal:
    """Converte uma entrada em `Decimal` quantizado em centavos.

    Aceita `str`, `int` e `Decimal`. Rejeita `float` com `TypeError` — passar um
    float é erro de programação, não erro de domínio, e falhar alto é o que
    impede a imprecisão de entrar no sistema.
    """
    if isinstance(valor, float):
        raise TypeError(
            "Dinheiro não pode vir de float (DT-01). "
            f"Use Decimal(str({valor!r})) ou passe a string diretamente."
        )
    if isinstance(valor, bool):
        raise TypeError("Dinheiro não pode vir de bool.")

    try:
        convertido = Decimal(valor) if not isinstance(valor, Decimal) else valor
    except (InvalidOperation, ValueError, TypeError):
        raise ValorInvalido("Informe um valor numérico válido.") from None

    if not convertido.is_finite():
        raise ValorInvalido("Informe um valor numérico válido.")

    return quantizar(convertido)


def quantizar(valor: Decimal) -> Decimal:
    """Arredonda para duas casas usando meio-para-cima, como se espera de dinheiro.

    O padrão do `Decimal` é `ROUND_HALF_EVEN`, que arredonda 0,005 para 0,00 —
    correto estatisticamente, surpreendente em um extrato.
    """
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def validar_positivo(valor: str | int | Decimal) -> Decimal:
    """Converte e exige valor estritamente positivo."""
    convertido = para_decimal(valor)
    if convertido <= ZERO:
        raise ValorInvalido()
    return convertido


def formatar(valor: Decimal) -> str:
    """Formata no padrão brasileiro: `R$ 1.234,56`."""
    corpo = f"{quantizar(valor):,.2f}"
    # troca separadores em uma passada, sem que a segunda desfaça a primeira
    corpo = corpo.translate(str.maketrans({",": ".", ".": ","}))
    return f"R$ {corpo}"
