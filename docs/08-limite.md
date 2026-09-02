> [Índice](README.md) · **08 — Limite de requisições**

# Limite de requisições

Cumpre a [RNF-3.9](fase-3-autenticacao.md), a única pendência do PRD original.

Protege duas coisas diferentes, por motivos diferentes.

## Força bruta no login

| Regra | Chave |
| --- | --- |
| 6 por 15 min | origem da requisição |
| 6 por 15 min | e-mail tentado |
| 10 por hora | origem, no cadastro |

**Por que duas chaves no login.** A de origem sozinha não impede um atacante com
muitos endereços de atacar uma conta específica. A de e-mail sozinha deixaria
alguém varrer muitas contas de um mesmo lugar. As duas juntas fecham os dois
lados.

**A senha certa também conta.** Se só as falhas contassem, bastaria acertar
qualquer conta pelo caminho para zerar o contador.

**O limite é verificado antes de chamar o GoTrue.** Verificar depois faria o
custo da força bruta recair sobre o serviço de autenticação, que é justamente o
que se quer poupar.

## Rajada na movimentação

30 por minuto, **por titular** — não por origem, e não por conta.

Duas pessoas atrás do mesmo NAT não deveriam competir pelo mesmo limite, e a
mesma pessoa em duas redes não deveria contornar o dela. Abrir uma segunda conta
também não renova a cota: quem move dinheiro é a pessoa.

Leitura não é limitada. Bloquear consulta de saldo puniria quem recarrega a
página, e não é isso que o limite existe para conter.

## A resposta

```
HTTP 429
Retry-After: 847

{"codigo": "LIMITE_EXCEDIDO",
 "mensagem": "Muitas tentativas (6 por 15 min). Aguarde 847s e tente de novo."}
```

O `Retry-After` é o que permite ao cliente esperar o tempo certo em vez de
insistir às cegas — e insistir às cegas é exatamente o que o limite contém.

## Duas limitações declaradas

### O contador vive na memória do processo

Isso é correto para o desenho atual — um container de backend, como no
`docker-compose.yml` — e **insuficiente para mais de uma réplica**: cada
processo contaria por si, e o limite efetivo seria multiplicado pelo número
delas.

A interface `Contador` existe exatamente para essa troca: substituir
`ContadorEmMemoria` por uma implementação sobre Redis ou sobre a própria tabela
do PostgreSQL não toca em nenhuma rota.

### `X-Forwarded-For` só é lido com proxy declarado

Por padrão, `CONFIAR_EM_PROXY=false` e o cabeçalho é ignorado.

Confiar nele sem essa declaração seria **pior que não ter limite nenhum**:
qualquer um forjaria uma origem diferente a cada requisição, e a proteção
estaria desligada aparentando existir. Um limite que não limita é pior que a
ausência dele, porque ninguém vai procurar o problema.

## Efeito nos testes

O limitador é único do processo — tem de ser, senão não contaria nada — e isso o
torna estado compartilhado entre casos de teste. Duas consequências, ambas
tratadas em `tests/api/conftest.py`:

- **`limite_zerado`**, autouse, zera o contador antes de cada caso. Sem ele, um
  teste gastaria a cota do seguinte e a suíte dependeria da ordem em que roda.
- **`sem_limite_de_movimentacao`**, declarada explicitamente pelos testes de
  concorrência. Eles disparam dezenas de requisições simultâneas para provar a
  atomicidade **do banco**, não do limitador; deixar o limite de produção valer
  ali faria o teste medir a coisa errada.
