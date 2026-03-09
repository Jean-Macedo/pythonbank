from datetime import datetime, date

class Cliente:
    def __init__(self, nome, data_nascimento, cpf, email, telefone):
        self.nome = nome
        self.data_nascimento = data_nascimento
        self.__cpf = cpf
        self.email = email
        self.telefone = telefone

    @property
    def nome(self):
        return self._nome

    @nome.setter
    def nome(self, novo_nome):
        if not novo_nome.strip():
            raise ValueError('O nome não pode estar vazio!')
        self._nome = novo_nome

    @property
    def email(self):
        return self._email
    
    @email.setter
    def email(self, novo_email):
        if not novo_email.strip():
            raise ValueError('O email não pode estar vazio!')
        self._email = novo_email
    
    @property
    def data_nascimento(self):
        return self._data_nascimento
    
    @data_nascimento.setter
    def data_nascimento(self, data_str):
        if isinstance(data_str, date):
            self._data_nascimento = data_str
            return
        try:
            data_convertida = datetime.strptime(data_str, "%d/%m/%Y").date()
            if data_convertida > date.today():
                raise ValueError("A data de nascimento não é válida")             
            self._data_nascimento = data_convertida
        except ValueError:
            raise ValueError("Formato de data inválido! Use DD/MM/AAAA")

    @property
    def telefone(self):
        return self._telefone
    
    @telefone.setter
    def telefone(self, numero):
        if not numero.isdigit():
            raise ValueError('Digite apenas números!')
        if len(numero) in [10,11]:
            self._telefone = numero
        else:
            raise ValueError('Número de telefone inválido!')

    @property
    def cpf(self):
        return self.__cpf
    
    @property
    def idade(self):
        hoje = date.today()
        idade = hoje.year - self._data_nascimento.year - (hoje.month, hoje.day) < (self._data_nascimento.month, self._data_nascimento.day)
        return idade