> [Índice](README.md) · **Fase 3 — Autenticação e autorização**

# Fase 3 — Autenticação e autorização

| | |
| --- | --- |
| **Depende de** | F1, F2 |
| **Bloqueia** | **F4** |
| **Estimativa** | 2–3 dias |
| **Entregável** | acesso restrito ao titular, verificado por teste automatizado |

Esta fase não existia no plano original e é a que separa um exercício de um
sistema. Sem ela, a API pública movimenta qualquer conta pelo número na URL.

> **Por que bloqueia a F4.** Um frontend escrito contra endpoints sem
> autenticação embute suposições — enviar identificadores no corpo, assumir uma
> conta implícita, não tratar `401` — que precisam ser desfeitas depois. Construir
> a interface antes custa retrabalho garantido.

## Autenticação

| ID | Requisito | Prio |
| --- | --- | --- |
| **RN-3.1** | Autenticação delegada ao **Supabase Auth** (GoTrue), que já roda no ambiente local da F1. O backend não armazena nem verifica senha. | P0 |
| **RN-3.2** | O backend valida a assinatura do JWT e resolve o cliente por `auth_user_id`. Token inválido ou expirado responde `401` em todas as rotas `/api`. | P0 |
| **RF-3.3** | `POST /auth/registro` cria o usuário no GoTrue **e** a linha em `clientes` **e** a conta corrente inicial. Falha em qualquer etapa não pode deixar cadastro pela metade. | P0 |
| **RF-3.4** | `POST /auth/refresh` renova o `access_token` sem exigir novo login. | P1 |

## Autorização em duas camadas

A verificação de titularidade da F2 cobre o caminho da API. A RLS cobre o acesso
**direto** ao banco — PostgREST, Studio, qualquer cliente com a chave anônima.

> **Correção.** O texto original dizia que a RLS cobriria "mesmo um bug de
> roteamento no Python". Não cobre: o backend conecta como dono do banco e dono
> ignora RLS. As duas camadas são independentes e protegem caminhos diferentes.
> Ver [DT-04](01-decisoes-tecnicas.md#dt-04).

| ID | Requisito | Prio |
| --- | --- | --- |
| **RN-3.5** | `enable row level security` nas três tabelas. Nenhuma delas fica sem política. | P0 |
| **RN-3.6** | Função auxiliar `cliente_atual()` resolve `auth.uid()` para `clientes.id`, usada por todas as políticas. | P0 |
| **RN-3.7** | Políticas de `select` restritas ao próprio cliente. **Nenhuma política concede `insert`, `update` ou `delete` direto** em `contas` ou `transacoes` — escrita só pelas funções RPC. | P0 |
| **RN-3.8** | A `service_role key` existe apenas no backend. O frontend nunca recebe chave de banco de nenhum tipo. | P0 |
| **RNF-3.9** | Rate limit no login e nos endpoints de movimentação. | P2 ✓ |

### Referência — políticas

`supabase/migrations/0003_rls.sql`

```sql
create or replace function cliente_atual() returns bigint
language sql stable security definer set search_path = public as $$
  select id from clientes where auth_user_id = auth.uid();
$$;

alter table clientes   enable row level security;
alter table contas     enable row level security;
alter table transacoes enable row level security;

create policy cliente_le_a_si_mesmo on clientes
  for select using (auth_user_id = auth.uid());

create policy cliente_le_suas_contas on contas
  for select using (cliente_id = cliente_atual());

create policy cliente_le_suas_transacoes on transacoes
  for select using (
    conta_id in (select id from contas where cliente_id = cliente_atual())
  );

-- nenhuma policy de insert/update/delete: escrita é exclusiva das funções RPC
```

## Testes desta fase

| ID | Requisito | Prio |
| --- | --- | --- |
| **RNF-3.10** | Teste que percorre **todas** as rotas com `{conta_id}` usando o token do cliente A contra uma conta do cliente B, e exige `404` em cada uma. Parametrizado sobre a lista de rotas do app, para que rota nova entre no teste automaticamente. | P0 |
| **RNF-3.11** | Teste que consulta o Supabase direto com a `anon key` do cliente A e confirma que nenhuma linha do cliente B retorna — valida a RLS isoladamente da camada Python. | P0 |
| **RNF-3.12** | Teste que tenta `insert` direto em `transacoes` com a `anon key` e exige recusa. | P1 |

O teste RNF-3.10 é parametrizado sobre `app.routes` justamente para que ninguém
precise lembrar de atualizá-lo. Rota nova com `{conta_id}` que não verifique
titularidade quebra a suíte sozinha.

## Definição de pronto

- [ ] Token do cliente A não lê nem move conta do cliente B em nenhuma rota — testado, não presumido ([CA-04](00-visao-e-escopo.md#critérios-de-aceite-globais)).
- [ ] Conta inexistente e conta alheia respondem `404` com a mesma mensagem.
- [ ] Requisição sem `Authorization` devolve `401` em todas as rotas `/api` ([CA-03](00-visao-e-escopo.md#critérios-de-aceite-globais)).
- [ ] Consulta direta ao Supabase com a `anon key` não retorna linha de outro cliente.
- [ ] `insert` direto em `transacoes` pelo cliente é recusado pela RLS.
- [ ] Registro que falha na criação da conta inicial não deixa cliente órfão.
- [ ] `git log -p | grep -iE "service_role|eyJ"` não retorna nada ([CA-05](00-visao-e-escopo.md#critérios-de-aceite-globais)).

## Riscos da fase

**RLS configurado errado expõe todos os clientes.** É silencioso: a aplicação
continua funcionando normalmente. Só o teste RNF-3.11, que consulta o banco
por fora do Python, detecta. Ele é obrigatório e roda no CI.

---

## Emendas aplicadas na execução

### O token é ES256, não HS256

O PRD supunha segredo compartilhado. O Supabase passa a assinar com **chave
assimétrica**: o `JWT_SECRET` que aparece no `supabase status` não valida token
nenhum — é resquício do esquema antigo. A validação usa o JWKS em
`/auth/v1/.well-known/jwks.json`, com as chaves públicas em cache.

É um erro fácil de cometer, porque o segredo está bem visível na saída do CLI e
a validação com ele falha em *toda* requisição, sem pista do motivo.

### A FK para `auth.users` entrou, e o seed mudou junto

Adiada da F1, criada aqui. O seed passou a inserir os usuários no `auth.users`
antes dos clientes, usando **apenas colunas da versão base do schema**: o seed
roda durante o *"Initialising schema"*, antes de o GoTrue subir e aplicar as
próprias migrações, então `email_confirmed_at` ainda não existe nesse momento.

Esses usuários servem para navegar no Studio. Quem precisa autenticar de fato
cria a conta pela API do GoTrue, que é o caminho real — e é o que os testes fazem.

### `CADASTRO_INCOMPLETO` é 403, não 401

Token válido cujo `sub` não tem `clientes` correspondente não é falha de
autenticação: o usuário **está** autenticado. É cadastro pela metade. A ação de
quem recebe é diferente — concluir o cadastro em vez de entrar de novo — então o
código também é.

### Compensação no cadastro

Criar usuário no GoTrue e criar o titular no banco são sistemas diferentes; não
há transação que abranja os dois. Se a etapa do banco falhar, o usuário do GoTrue
é removido.

Sem isso sobraria um login que existe e não leva a lugar nenhum, e — pior — uma
segunda tentativa com o mesmo e-mail bateria em "já cadastrado" para sempre. Há
teste para exatamente esse caminho.

### As funções de movimentação não são expostas ao PostgREST

`realizar_deposito` e companhia **não verificam titularidade** — quem verifica é
a API. Concedê-las a `authenticated` permitiria a qualquer portador de token
depositar e sacar em conta alheia passando o id pela RPC. O `execute` foi revogado
de `public`, `anon` e `authenticated`; só o backend, como dono, as invoca.

### RNF-3.9 — limite de requisições

Feito depois das fases, e detalhado em [Limite de requisições](08-limite.md).

Duas proteções distintas: força bruta no login (6 por 15 min, por origem **e**
por e-mail) e automação descontrolada na movimentação (30 por minuto, por
titular). Resposta `429` com `Retry-After`.

Duas decisões que valem registrar:

**O contador vive na memória do processo.** É honesto para um container, e
insuficiente para várias réplicas — cada uma contaria por si. A interface
`Contador` existe para que trocar por Redis não toque em nenhuma rota.

**`X-Forwarded-For` só é lido com `CONFIAR_EM_PROXY=true`.** Confiar por padrão
seria pior que não ter limite: forjar o cabeçalho daria uma chave nova a cada
requisição, desligando a proteção enquanto ela aparenta existir.

### A `DT-04` foi corrigida, não cumprida

Ver [Decisões técnicas](01-decisoes-tecnicas.md#dt-04). A promessa de que a RLS
cobriria bug de roteamento não se sustenta com o backend conectando como dono do
banco. O texto foi ajustado para descrever o que o código faz.
