from datetime import datetime

class Conta:
    def __init__(self, cliente_objeto):
        self._cliente = cliente_objeto
        self.__saldo = 0
        self._historico = []

    @property
    def saldo(self):
        return self.__saldo
    
    def depositar(self, valor):
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if valor > 0:
            self.__saldo += valor
            self._historico.append(f'[{data_hora}] Depósito: + R${valor:.2f}')
            return f'Depósito de R${valor:.2f} efetuado com sucesso.'
        else:
            raise ValueError(f'O valor a ser depositado deve ser positivo!')

    def sacar(self, valor):
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if valor <= 0:
            raise ValueError(f'O valor a ser sacado deve ser positivo!')
        if valor > self.__saldo:
            raise ValueError(f'Saldo insuficiente! Seu saldo é de R${self.__saldo:.2f}')
        else:
            self.__saldo -= valor
            self._historico.append(f'[{data_hora}] Saque: - R${valor:.2f}')
            return f'Saque de R${valor:.2f} efetuado com sucesso.'
        
    def obter_dados_extrato(self):
            return {
                "titular": self._cliente.nome,
                "cpf": self._cliente.cpf,
                "historico": self._historico,
                "saldo_atual": self.__saldo
            }