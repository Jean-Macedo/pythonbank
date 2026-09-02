> [Índice](README.md) · **07 — Estorno**

# Estorno

O primeiro recurso construído depois das seis fases. Entrou sem alterar o modelo
de dados de forma estrutural, e é essa a razão de ter sido escolhido: a
[DT-03](01-decisoes-tecnicas.md#dt-03) dizia desde a Fase 1 que *"correção é uma
transação nova de sinal oposto, nunca um `update` ou `delete` no histórico"*.
Aqui a frase virou comportamento verificável.

## O que acontece

Estornar cria um lançamento **novo**, de sinal oposto, com `estorno_de`
apontando para o original. O lançamento estornado não é apagado, marcado nem
alterado — ele continua no extrato, ao lado do estorno.

```
deposito             +R$ 200,00
estorno_saida        −R$ 200,00   estorno_de → o depósito acima
```

## Quem pode estornar o quê

| Lançamento | Efeito | Condição |
| --- | --- | --- |
| `deposito` | devolve o dinheiro (débito) | exige saldo |
| `saque` | devolve o dinheiro (crédito) | — |
| `transferencia_saida` | desfaz as duas pernas | exige saldo no destino |
| `transferencia_entrada` | **não é permitido** | — |
| um estorno | **não é permitido** | — |

**Por que quem recebeu não estorna.** Permitir isso deixaria alguém puxar de
volta dinheiro de uma conta alheia sem que o dono agisse. Para devolver, faz-se
uma transferência nova — que é uma decisão de quem tem o dinheiro, não de quem
o enviou.

## Concorrência

Um lançamento só pode ser estornado uma vez, e isso é imposto em dois níveis:

- `select ... for update` no original, antes de qualquer verificação
- índice único parcial em `estorno_de`

Sem eles, dez pedidos simultâneos passariam todos pela checagem de "ainda não
estornado" antes de qualquer um escrever, e o dinheiro sairia dez vezes. É a
mesma corrida corrigida no limite de contas — e há teste que a reproduz.

## A janela de prazo

`JANELA_DE_ESTORNO_DIAS = 7`, definida em `backend/core/conta.py`. O número vem
do Python e o banco o aplica **dentro da mesma transação**, exatamente como o
limite de contas: política é da aplicação, atomicidade é do banco
([DT-05](01-decisoes-tecnicas.md#dt-05)).

## Reconciliação

A view `contas_divergentes` passou a somar `estorno_entrada` como entrada e
`estorno_saida` como saída. Sem isso, **toda conta com estorno apareceria como
divergente** e o [CA-02](00-visao-e-escopo.md#critérios-de-aceite-globais) —
o critério mais importante do projeto — falharia por engano.

## Códigos de erro

| Código | HTTP | Quando |
| --- | --- | --- |
| `LANCAMENTO_NAO_ENCONTRADO` | 404 | não existe, ou é de outra conta |
| `JA_ESTORNADO` | 409 | já foi desfeito |
| `ESTORNO_DE_ESTORNO` | 422 | tentou estornar um estorno |
| `ESTORNO_NAO_PERMITIDO` | 422 | quem recebeu tentando desfazer |
| `FORA_DA_JANELA_DE_ESTORNO` | 422 | passou dos 7 dias |
| `SALDO_INSUFICIENTE` | 422 | sem saldo para devolver um depósito |
| `SALDO_INSUFICIENTE_NO_DESTINO` | 422 | destino da transferência já gastou |

Lançamento inexistente e lançamento alheio respondem **o mesmo 404**, pelo mesmo
motivo que contas alheias respondem: distinguir permitiria enumerar.

## Rota

```
POST /api/contas/{conta_id}/lancamentos/{transacao_id}/estorno
```

Sob a conta, não sob a transação, porque a titularidade é da conta —
`get_conta_do_cliente` resolve e verifica o dono, e o lançamento é reconferido
contra ela dentro da função PL/pgSQL. Saber o id de um lançamento alheio não
basta.
