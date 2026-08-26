> [Índice](README.md) · **Fase 1 — Persistência transacional**

# Fase 1 — Persistência transacional

| | |
| --- | --- |
| **Depende de** | F0 |
| **Bloqueia** | F2 |
| **Estimativa** | 3–4 dias |
| **Entregável** | Supabase local rodando com schema, funções e migrações versionadas |

O banco deixa de ser um depósito passivo e passa a ser onde a integridade é
imposta. Se a aplicação tiver um bug, o banco ainda recusa saldo negativo.

## Ambiente local

Esta fase estabelece o ciclo de desenvolvimento de todo o resto do projeto
([DT-06](01-decisoes-tecnicas.md#dt-06)).

| ID | Requisito | Prio |
| --- | --- | --- |
| **RNF-1.1** | Instalar o Supabase CLI e rodar `supabase init` na raiz. O diretório `supabase/` é versionado. | P0 |
| **RNF-1.2** | `supabase start` sobe PostgreSQL, GoTrue e PostgREST locais. As credenciais impressas no start alimentam o `.env` de desenvolvimento. | P0 |
| **RNF-1.3** | Toda alteração de schema nasce como arquivo em `supabase/migrations/`, numerado e idempotente. **Nenhuma mudança feita clicando no painel.** | P0 |
| **RNF-1.4** | `supabase db reset` recria o banco do zero a partir das migrações. Este é o comando que precede cada rodada de testes de integração. | P0 |
| **RNF-1.5** | `supabase/seed.sql` cria dois clientes com três contas no total, para desenvolvimento manual e para o teste de isolamento da F3. | P1 |

> O projeto na nuvem só é criado na F5, e recebe exatamente as mesmas migrações.
> Se `supabase db push` exigir alguma correção manual, a migração estava errada.

## Schema

| ID | Requisito | Prio |
| --- | --- | --- |
| **RF-1.6** | Aplicar o DDL de [Modelo de dados](02-modelo-de-dados.md#ddl) como `0001_schema_inicial.sql`, com todas as constraints `check` e `unique`. | P0 |
| **RF-1.7** | O diagrama ER em Mermaid vive no próprio documento de modelo — renderiza no GitHub e é versionado junto do DDL. Dispensa ferramenta externa. | P2 |
| **RN-1.8** | Numeração de conta gerada por sequence no banco, não pela aplicação. Duas aberturas simultâneas não podem produzir o mesmo número. | P0 |

## Funções de movimentação

| ID | Requisito | Prio |
| --- | --- | --- |
| **RN-1.9** | `realizar_deposito`, `realizar_saque`, `transferir` e `encerrar_conta` em PL/pgSQL, cada uma atualizando saldo e inserindo no ledger na mesma transação. ([DT-02](01-decisoes-tecnicas.md#dt-02)) | P0 |
| **RN-1.10** | Saldo insuficiente é bloqueado pela cláusula `where` do `update`, **não** por um `select` anterior à escrita. Não pode existir janela entre verificar e escrever. | P0 |
| **RN-1.11** | `transferir` adquire lock nas duas contas em **ordem crescente de `id`** antes de qualquer `update`. Sem isso, A→B e B→A simultâneas travam uma na outra. | P0 |
| **RN-1.12** | Toda exceção usa os códigos estáveis da [tabela de erros](03-contrato-api.md#mapeamento-de-erros) — nunca mensagem livre. | P0 |
| **RN-1.13** | Operação sobre conta inativa levanta `CONTA_NAO_ENCONTRADA`. | P1 |

## Testes desta fase

Rodam contra o Supabase local, com `supabase db reset` antes de cada suíte.

| ID | Requisito | Prio |
| --- | --- | --- |
| **RNF-1.14** | Teste de concorrência: 50 depósitos simultâneos de `1.00` na mesma conta resultam em saldo exatamente `50.00`. É o teste que prova [DT-02](01-decisoes-tecnicas.md#dt-02) — ele falha no modelo *read-modify-write*. | P0 |
| **RNF-1.15** | Teste de deadlock: transferências A→B e B→A disparadas em paralelo, ambas concluem. | P1 |
| **RNF-1.16** | A [query de reconciliação](02-modelo-de-dados.md#reconciliação) retorna zero linhas após mil operações aleatórias. | P0 |

## Definição de pronto

- [ ] `supabase db reset` reconstrói o banco inteiro sem intervenção manual.
- [ ] 50 depósitos concorrentes de `1.00` resultam em `50.00`, não menos.
- [ ] Saque acima do saldo levanta `SALDO_INSUFICIENTE` e **não deixa registro** em `transacoes`.
- [ ] `insert` direto em `contas` com saldo negativo é recusado pela constraint.
- [ ] Transferências cruzadas simultâneas não produzem deadlock.
- [ ] `update` direto em `transacoes` é possível apenas para o superusuário — o ledger é append-only na prática.
- [ ] A query de reconciliação retorna zero linhas ([CA-02](00-visao-e-escopo.md#critérios-de-aceite-globais)).

## Riscos da fase

**Regra de negócio migrando para o SQL.** As funções PL/pgSQL são atraentes e é
fácil enfiar política dentro delas — limite de contas, elegibilidade, regras de
tarifa. Não faça: o SQL impõe *integridade*, o Python impõe *política*
([DT-05](01-decisoes-tecnicas.md#dt-05)). A revisão dessa fronteira acontece ao
fim da F2.
