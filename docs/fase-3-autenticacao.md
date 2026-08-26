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

A verificação de titularidade da F2 é a primeira camada. RLS é a segunda,
independente: mesmo um bug de roteamento no Python não vaza dados.

| ID | Requisito | Prio |
| --- | --- | --- |
| **RN-3.5** | `enable row level security` nas três tabelas. Nenhuma delas fica sem política. | P0 |
| **RN-3.6** | Função auxiliar `cliente_atual()` resolve `auth.uid()` para `clientes.id`, usada por todas as políticas. | P0 |
| **RN-3.7** | Políticas de `select` restritas ao próprio cliente. **Nenhuma política concede `insert`, `update` ou `delete` direto** em `contas` ou `transacoes` — escrita só pelas funções RPC. | P0 |
| **RN-3.8** | A `service_role key` existe apenas no backend. O frontend nunca recebe chave de banco de nenhum tipo. | P0 |
| **RNF-3.9** | Rate limit no login e nos endpoints de movimentação. | P2 |

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
