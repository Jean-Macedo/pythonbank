"""Testes que guardam as fronteiras arquiteturais, não o comportamento.

A definição de pronto da Fase 0 pede algumas checagens sobre `core/` (nada de
`float`, nada de infraestrutura, nada de `ValueError` solto). Feitas por `grep`,
elas valem no dia em que alguém lembra de rodar. Feitas por AST na suíte, valem
sempre — e é a suíte que impede a Fase 2 de vazar FastAPI para dentro do domínio.
"""

import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MODULOS_DO_DOMINIO = sorted((RAIZ / "core").glob("*.py"))

INFRAESTRUTURA_PROIBIDA = {
    "supabase",
    "fastapi",
    "pydantic",
    "requests",
    "httpx",
    "sqlalchemy",
    "psycopg",
    "psycopg2",
}

CHAMADAS_PROIBIDAS = {"input", "print", "float"}


def arvore(caminho: pathlib.Path) -> ast.Module:
    return ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))


def raizes_importadas(no: ast.AST) -> set[str]:
    modulos = set()
    for filho in ast.walk(no):
        if isinstance(filho, ast.Import):
            modulos.update(alias.name.split(".")[0] for alias in filho.names)
        elif isinstance(filho, ast.ImportFrom) and filho.module:
            modulos.add(filho.module.split(".")[0])
    return modulos


def test_existem_modulos_para_verificar():
    """Guarda contra um glob vazio fazendo os testes abaixo passarem à toa."""
    assert len(MODULOS_DO_DOMINIO) >= 5


@pytest.mark.parametrize("modulo", MODULOS_DO_DOMINIO, ids=lambda p: p.name)
class TestDominioIsolado:
    def test_nao_importa_infraestrutura(self, modulo):
        """DT-05 — o domínio não conhece banco, HTTP nem serialização."""
        proibidos = raizes_importadas(arvore(modulo)) & INFRAESTRUTURA_PROIBIDA
        assert not proibidos, f"{modulo.name} importa {sorted(proibidos)}"

    def test_nao_chama_input_print_nem_float(self, modulo):
        """DT-01 e DT-05 — nem apresentação, nem ponto flutuante."""
        encontradas = {
            no.func.id
            for no in ast.walk(arvore(modulo))
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id in CHAMADAS_PROIBIDAS
        }
        assert not encontradas, f"{modulo.name} chama {sorted(encontradas)}"

    def test_so_levanta_erros_de_dominio(self, modulo):
        """RF-0.13 — nenhum `raise ValueError` genérico sobrevive no domínio.

        `TypeError` e `ErroDeProgramacao` são as exceções deliberadas: sinalizam
        bug, não estado de negócio inválido, e não devem virar mensagem de
        usuário.
        """
        permitidos = {"TypeError", "ErroDeProgramacao"}
        levantados = set()

        for no in ast.walk(arvore(modulo)):
            if not isinstance(no, ast.Raise) or no.exc is None:
                continue
            alvo = no.exc.func if isinstance(no.exc, ast.Call) else no.exc
            if isinstance(alvo, ast.Name):
                levantados.add(alvo.id)

        genericos = {
            nome
            for nome in levantados
            if nome not in permitidos and not _e_erro_de_dominio(nome)
        }
        assert not genericos, f"{modulo.name} levanta {sorted(genericos)}"


def _e_erro_de_dominio(nome: str) -> bool:
    from core import erros

    classe = getattr(erros, nome, None)
    return isinstance(classe, type) and issubclass(classe, erros.ErroDeDominio)


class TestApresentacaoNaoTemRegra:
    def test_cli_nao_importa_infraestrutura(self):
        proibidos = raizes_importadas(arvore(RAIZ / "interface.py"))
        assert not (proibidos & INFRAESTRUTURA_PROIBIDA)

    def test_cli_nao_calcula_dinheiro(self):
        """A CLI formata e delega; aritmética monetária é do domínio."""
        proibidos = raizes_importadas(arvore(RAIZ / "interface.py"))
        assert "decimal" not in proibidos
