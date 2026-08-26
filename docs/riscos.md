> [Índice](README.md) · **Apêndice — Riscos**

# Riscos

Riscos transversais ao projeto. Cada fase carrega ainda os seus próprios, na
seção final do respectivo documento.

## Alto

### Regra de negócio migra para o SQL e o domínio Python esvazia

As funções PL/pgSQL da F1 são atraentes e é fácil enfiar política dentro delas —
limite de contas, elegibilidade, tarifas. Se isso acontecer, o projeto perde
exatamente o que se propôs a demonstrar: POO aplicada.

**Mitigação.** A fronteira de [DT-05](01-decisoes-tecnicas.md#dt-05): o SQL
impõe *integridade* (não-negatividade, atomicidade, unicidade), o Python impõe
*política* (regras que mudam sem migração). Revisão explícita da fronteira na
definição de pronto da F2.

### RLS configurado errado expõe dados de todos os clientes

O modo de falha é silencioso: a aplicação continua funcionando normalmente
porque a camada Python filtra corretamente. Só uma consulta feita **por fora**
do backend revela o problema.

**Mitigação.** [RNF-3.11](fase-3-autenticacao.md) consulta o Supabase direto
com a `anon key` de um cliente e exige que nenhuma linha de outro apareça. Roda
no CI, não sob demanda.

### Rota nova esquece a verificação de titularidade

Com várias contas por cliente, todo endpoint de movimentação recebe um
`conta_id` na URL. Uma rota adicionada meses depois, sem a dependência de
titularidade, abre o sistema inteiro.

**Mitigação.** A verificação existe em um único lugar
([RN-2.5](fase-2-api-rest.md)) e o teste [RNF-3.10](fase-3-autenticacao.md) é
parametrizado sobre `app.routes` — rota nova entra no teste automaticamente e
quebra a suíte se não verificar.

## Médio

### Escopo cresce e o projeto para na metade

**Mitigação.** Cada fase entrega algo executável e demonstrável. F0 a F2 já
formam um sistema completo pela API, sem depender da F4. O
[Fora de escopo](fora-de-escopo.md) existe para fechar discussões, não para
registrar desejos.

### Precisão decimal se perde na borda JSON/JavaScript

`JSON.parse` converte número em `float` de 64 bits, desfazendo silenciosamente
o cuidado de [DT-01](01-decisoes-tecnicas.md#dt-01).

**Mitigação.** Valores trafegam como string e o frontend nunca faz aritmética
monetária ([RN-4.3](fase-4-interface.md)). O saldo exibido é sempre o que a API
devolveu.

### Divergência entre schema local e schema da nuvem

Corrigir algo clicando no painel do Supabase deixa a nuvem à frente das
migrações, e a próxima `db push` falha ou sobrescreve.

**Mitigação.** [DT-06](01-decisoes-tecnicas.md#dt-06): nenhuma alteração nasce
no painel. Detecção com `supabase db diff`, que deve vir vazio.

## Baixo

### O CLI é abandonado durante a F0

Ele é descartado nas fases seguintes, então há pouca motivação para mantê-lo
funcionando. Mas enquanto roda sobre `core/` sem importar infraestrutura, é a
prova prática de que a separação de [DT-05](01-decisoes-tecnicas.md#dt-05)
existe de fato.

**Mitigação.** Está na definição de pronto da [F0](fase-0-dominio.md).

### Conflito de porta com o Supabase local

O CLI ocupa `54321`, `54322` e `54323`. Colisão com outro projeto rodando na
mesma máquina.

**Mitigação.** Portas declaradas em `supabase/config.toml`, versionado.
