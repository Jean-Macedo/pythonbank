from cliente import Cliente
from conta import Conta
import time

def menu():
    print("\n" + "="*20)
    print("  BANCO JEAN ")
    print("="*20)
    print("1 - Cadastrar Cliente e Abrir Conta")
    print("2 - Depositar")
    print("3 - Sacar")
    print("4 - Ver Extrato")
    print("0 - Sair")
    return int(input(f'Escolha um opção: '))   

conta_ativa = None

while True:
    opcao = menu()
    
    if opcao == 1:
        try:
            nome = input(f'Digite seu nome: ')
            data_nascimento = input(f'Data de nascimento: (DD/MM/AAAA): ')
            cpf = input(f'Digite seu CPF (apenas números): ')
            email = input(f'Digite seu e-mail: ')
            tel = input(f'Digite seu telefone: ')

            novo_cliente = Cliente(nome, data_nascimento, cpf, email, tel)
            conta_ativa = Conta(novo_cliente)
            print(f'\n ✅ Conta aberta com sucesso!')
        except ValueError as e:
            print(f'\n ⚠️ Erro no cadastro {e}')

    if opcao == 2:
        if conta_ativa:
            try:
                valor = float(input(f'Digite o valor que deseja depositar: '))
                print(f'{conta_ativa.depositar(valor)}')
            except ValueError as e:
                print(f'\n ⚠️ Erro: Nenhuma conta cadastrada.')

    if opcao == 3:
        if conta_ativa:
            try:
                valor = float(input(f'Digite o valor que deseja sacar: '))
                print(f'{conta_ativa.sacar(valor)}')
            except ValueError as e:
                print(f'\n ⚠️ Operação negada! Saldo insuficiente.')
            else:
                print(f'⚠️ Erro: Nenhuma conta cadastrada.')
    
    if opcao == 4:
        if conta_ativa:
            dados = conta_ativa.obter_dados_extrato()
            print("\n" + "-"*30)
            print(f"EXTRATO: {dados['titular']}")
            print(f"CPF: {dados['cpf']}")
            print("-" * 30)
            for dado in dados['historico']:
                print(dado)
            print(f'Saldo atual: R${dados['saldo_atual']:.2f}')
            print(f'-'*30)
        else:
            print(f'⚠️ Nenhuma conta ativa!')

    elif opcao == 0:
        print(f'Desconectando do sistema..')
        time.sleep(3)
        print(f'Desconectado. Volte sempre {nome}!')
    else:
        print(f'⚠️ Opção inválida!')