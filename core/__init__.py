"""Domínio do Banco Jean.

Este pacote não conhece banco de dados, HTTP nem terminal (DT-05). Tudo aqui é
testável sem infraestrutura — é a garantia de que a lógica de negócio sobrevive
à troca de qualquer camada em volta.
"""

from core.cliente import Cliente
from core.conta import Conta, TipoConta
from core.erros import ErroDeDominio
from core.eventos import TipoTransacao, Transacao

__all__ = [
    "Cliente",
    "Conta",
    "TipoConta",
    "ErroDeDominio",
    "Transacao",
    "TipoTransacao",
]
