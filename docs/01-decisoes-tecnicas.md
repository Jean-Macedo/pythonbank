> [Índice](README.md) · **01 — Decisões técnicas**

# Decisões técnicas

Seis decisões que valem para todas as fases. Cada uma corrige um problema
estrutural do plano original e deve ser tratada como **restrição, não como
sugestão**. Os requisitos das fases referenciam estes identificadores — quando
surgir a pergunta "por que assim?" durante a implementação, a resposta tem
endereço.

---

<a id="dt-01"></a>
## DT-01 — Dinheiro é `Decimal`, nunca `float`

**Decisão.** `NUMERIC(15,2)` no PostgreSQL, `decimal.Decimal` no Python,
`condecimal(gt=0, max_digits=15, decimal_places=2)` no Pydantic. No JSON os
valores trafegam como **string**; no frontend são formatados com
`Intl.NumberFormat('pt-BR')` e nunca somados em JavaScript.

**Por quê.** Ponto flutuante binário não representa 0,10 exatamente. Somando
milhares de transações o saldo diverge de centavos, e em um banco isso é
defeito, não arredondamento. A conversão de entrada usa `Decimal(str(valor))` —
`Decimal(0.1)` reintroduz o erro que se está tentando evitar.

**Consequência.** JSON não tem tipo decimal. Serializar como número faria o
JavaScript reconverter para `float` na borda; por isso a string.

---

<a id="dt-02"></a>
## DT-02 — Movimentação acontece dentro de uma função PostgreSQL

**Decisão.** Depósito, saque e transferência são funções PL/pgSQL invocadas por
`supabase.rpc()`. O Python não lê o saldo, calcula e regrava — ele chama uma
operação que já é atômica.

**Por quê.** "Inserir transação" e "atualizar saldo" como duas chamadas HTTP
separadas não são atômicas: a segunda pode falhar e deixar um registro que nunca
moveu dinheiro. Pior, `saldo = saldo_lido + valor` em Python é
*read-modify-write* — duas operações concorrentes e uma sobrescreve a outra
silenciosamente.

**Consequência.** Saldo insuficiente é bloqueado pela cláusula `where` do
`update`, não por um `if` anterior à escrita. A verificação e a escrita
acontecem no mesmo comando.

---

<a id="dt-03"></a>
## DT-03 — Saldo é coluna mantida, ledger é a verdade

**Decisão.** `contas.saldo` existe por desempenho, mas só é alterado dentro da
mesma transação que insere em `transacoes`. Uma query de reconciliação roda nos
testes e valida que os dois concordam.

**Por quê.** Saldo desnormalizado é rápido de ler e fácil de corromper. Amarrar
as duas escritas à mesma transação dá a velocidade sem abrir mão da auditoria.

**Consequência.** `transacoes` é append-only. Correção de erro é uma transação
nova de sinal oposto, nunca um `update` ou `delete` no histórico.

---

<a id="dt-04"></a>
## DT-04 — A conta vem da URL, a titularidade vem do token

**Decisão.** Como um cliente tem várias contas, o `conta_id` aparece no caminho
da rota (`/api/contas/{conta_id}/deposito`) — **nunca no corpo**. Toda rota que
recebe um `conta_id` resolve o cliente pelo `sub` do JWT e verifica a
titularidade antes de qualquer ação. RLS ativo nas três tabelas como segunda
barreira independente.

**Conta que existe mas não é sua responde `404`, não `403`.** Um `403` confirma
que o identificador existe e permite enumerar as contas do banco inteiro.

**Por quê.** Se o `conta_id` vem do corpo sem verificação, trocar `1` por `2` no
DevTools saca da conta de outra pessoa. A verificação é implementada uma única
vez, como dependência do FastAPI, e não repetida em cada handler — repetição é
onde uma rota acaba esquecida.

**Consequência.** A checagem de titularidade é um ponto único de falha
deliberado: um teste que tenta acessar conta alheia por *cada* rota é
obrigatório ([CA-04](00-visao-e-escopo.md#critérios-de-aceite-globais)).

---

<a id="dt-05"></a>
## DT-05 — O domínio não conhece o banco

**Decisão.** `core/` contém classes puras que validam regras e não importam
`supabase`, `fastapi` nem chamam `input()`. Os repositórios em `infra/` traduzem
entre domínio e persistência.

A fronteira: **o SQL impõe integridade** — não-negatividade, atomicidade,
unicidade. **O Python impõe política** — limite de contas por cliente,
elegibilidade, formatação, regras que mudam sem migração.

**Por quê.** É o que preserva o propósito do projeto. Sem essa separação, o
endpoint faz tudo inline e as classes viram código morto — o POO some justamente
no documento que diz aplicá-lo.

---

<a id="dt-06"></a>
## DT-06 — Desenvolvimento roda no Supabase local

**Decisão.** O ciclo de desenvolvimento usa o **Supabase CLI** (`supabase
start`), que sobe PostgreSQL, GoTrue e PostgREST em containers locais. O projeto
na nuvem existe apenas para a demonstração final e recebe as mesmas migrações.

**Por quê.** Latência de rede em cada teste torna o ciclo insuportável.
`supabase db reset` recria o banco do zero a partir das migrações em segundos —
isso só é viável localmente, e é o que torna os testes de integração
descartáveis e confiáveis.

**Consequência.** As migrações em `supabase/migrations/` deixam de ser
documentação e passam a ser o mecanismo real de evolução do schema. Nenhuma
alteração é feita clicando no painel: toda mudança nasce como arquivo
versionado.

**Serviços desligados (aplicado na F1).** `storage`, `realtime`, `edge_runtime` e
`analytics` estão com `enabled = false` no `config.toml`. Os três primeiros
segfaltam (`exit 139`) no ambiente de desenvolvimento atual — Windows + WSL2 —
derrubando o `supabase start` inteiro, e nenhum deles é usado por este projeto.
Ficam de pé apenas `db`, `auth`, `rest`, `kong`, `studio` e `inbucket`, que é o
necessário até a Fase 4.

---

## Resumo

| ID | Decisão | Fase onde entra |
| --- | --- | --- |
| DT-01 | `Decimal` de ponta a ponta | F0 |
| DT-02 | Movimentação em função PL/pgSQL | F1 |
| DT-03 | Ledger é a verdade, saldo é cache | F1 |
| DT-04 | Conta na URL, titularidade no token | F2, F3 |
| DT-05 | Domínio isolado de infraestrutura | F0, F2 |
| DT-06 | Supabase local no desenvolvimento | F1 |
