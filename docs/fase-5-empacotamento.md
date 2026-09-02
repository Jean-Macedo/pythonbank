> [Índice](README.md) · **Fase 5 — Empacotamento**

# Fase 5 — Empacotamento

| | |
| --- | --- |
| **Depende de** | F2, F4 |
| **Bloqueia** | — |
| **Estimativa** | 1–2 dias |
| **Entregável** | `docker compose up` sobe o sistema; projeto na nuvem para demonstração |

## Como Docker convive com o Supabase local

O Supabase CLI **já roda seus próprios containers** (`supabase start`). O
`docker-compose.yml` deste projeto sobe apenas backend e frontend, e aponta para
o Supabase local pela rede do host. Não duplique o PostgreSQL — dois bancos no
mesmo projeto é fonte garantida de confusão sobre qual está sendo migrado.

| Ambiente | Banco | Como sobe |
| --- | --- | --- |
| Desenvolvimento | Supabase CLI local | `supabase start` + `docker compose up` |
| Demonstração | Projeto Supabase na nuvem | `docker compose up` com `.env` de produção |

## Requisitos

| ID | Requisito | Prio |
| --- | --- | --- |
| **RNF-5.1** | Segredos em `.env` na raiz, carregados por `env_file`. `.env` no `.gitignore`, com `.env.example` versionado listando toda variável necessária. | P0 |
| **RNF-5.2** | Remover a chave `version:` do compose — obsoleta no Compose v2 e emite warning. | P2 |
| **RNF-5.3** | Frontend em build multi-stage servido por nginx. O dev server do Vite não vai para produção. | P1 |
| **RNF-5.4** | `healthcheck` no backend usando `/health` (RF-2.9), e `depends_on: condition: service_healthy` no frontend. `depends_on` simples espera o container iniciar, não ficar pronto. | P1 |
| **RNF-5.5** | `supabase db push` aplica as migrações da F1 no projeto da nuvem **sem nenhuma correção manual**. Se exigir ajuste, a migração estava errada. | P0 |
| **RNF-5.6** | README na raiz com passo a passo verificado em máquina limpa, incluindo a instalação do Supabase CLI. | P1 |
| **RNF-5.7** | CI no GitHub Actions rodando `ruff`, `pytest` e a suíte de integração contra o Supabase local. | P2 |

## docker-compose.yml

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    extra_hosts:
      # alcança o Supabase local rodando no host
      - "host.docker.internal:host-gateway"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 3s
      retries: 5

  frontend:
    build: ./frontend
    ports: ["5173:80"]
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      backend:
        condition: service_healthy
```

## .env.example

```dotenv
# Supabase — local: valores impressos por `supabase start`
SUPABASE_URL=http://host.docker.internal:54321
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=

# CORS
CORS_ORIGINS=http://localhost:5173
```

A `anon key` não aparece aqui: o backend usa exclusivamente a `service_role`
([RN-3.8](fase-3-autenticacao.md)), e o frontend não recebe chave de banco de
nenhum tipo.

## Definição de pronto

- [ ] `git clone`, `supabase start`, `cp .env.example .env`, `docker compose up` entregam o sistema funcionando.
- [ ] `docker compose config` não emite nenhum warning.
- [ ] `.env.example` lista toda variável que a aplicação exige — subir sem nenhuma delas falha com mensagem clara.
- [ ] Nenhum valor de segredo aparece em arquivo versionado ([CA-05](00-visao-e-escopo.md#critérios-de-aceite-globais)).
- [ ] `supabase db push` aplica as migrações na nuvem sem intervenção manual.
- [ ] O passo a passo do README foi executado em uma máquina que nunca rodou o projeto.

## Riscos da fase

**Divergência entre o schema local e o da nuvem.** Acontece quando alguém
corrige algo clicando no painel do Supabase em vez de escrever migração. A
prevenção é a disciplina de [DT-06](01-decisoes-tecnicas.md#dt-06); a detecção
é `supabase db diff`, que deve vir vazio contra os dois ambientes.

---

## Emendas aplicadas na execução

### `VITE_API_URL` como variável do container não funciona

O `docker-compose.yml` do PRD passava `VITE_API_URL` em `environment:`. **Isso
não tem efeito nenhum.** O Vite substitui `import.meta.env` por literais durante
`npm run build`: o valor fica gravado no bundle, e nenhuma variável de ambiente
o altera depois.

Verificado: compilei com um valor-sentinela e o encontrei cru no `.js` gerado.

A falha seria silenciosa — a imagem subiria apontando para o endereço de quem a
compilou, e ninguém veria erro. Mesma classe do `response.ok` da Fase 4.

**Solução.** `public/config.js` é reescrito pelo entrypoint do nginx na subida
do container, a partir de `API_URL`. O `index.html` o carrega antes do bundle, e
`client.ts` prefere `window.__BANCO_CONFIG__` a `import.meta.env`. Assim o mesmo
artefato serve qualquer ambiente — que é o que torna verdadeira a frase "a
imagem testada é a imagem publicada".

### Emissor do JWT separado do endereço de rede

Descoberto ao subir a stack: o cadastro funcionava e **toda** requisição
autenticada seguinte devolvia 401.

O GoTrue carimba no `iss` o endereço que ele conhece — `127.0.0.1:54321` — e o
backend em container o alcança por `host.docker.internal`. A validação de
emissor da Fase 3 derivava o esperado da URL de conexão, tratando identidade
pública e endereço de rede como a mesma coisa.

Agora são duas configurações: `SUPABASE_URL` para conectar, `SUPABASE_ISSUER`
para validar. Vazio, o segundo deriva do primeiro — que é o caso local.

O sintoma era confuso justamente porque o token estava perfeito.

### O compose não exige editar o `.env`

Primeira versão pedia trocar `127.0.0.1` por `host.docker.internal` no `.env`.
Isso quebra os testes locais: esse nome só resolve dentro de container.

O `docker-compose.yml` passou a sobrescrever `DATABASE_URL` e `SUPABASE_URL` no
próprio `environment:`, que tem precedência sobre `env_file`. O `.env` fica
sempre com valores locais, e `docker compose up` funciona sem edição nenhuma.

### O que mais entrou

- Backend roda como usuário sem privilégio, `uid 10001`
- Dependências copiadas antes do código, para a camada não ser refeita a cada
  edição de arquivo Python
- `nginx.conf` com `try_files` para as rotas do React, `no-store` no
  `config.js` — que muda a cada subida — e cache longo em `/assets/`, cujos
  nomes têm hash
- CI no GitHub Actions em quatro trabalhos: domínio e lint sem banco (o que
  prova que ele não depende de infraestrutura), integração contra um PostgreSQL
  de serviço, frontend, e construção das duas imagens

---

## As duas pendências

### RNF-5.6 — passo a passo verificado em clone limpo

Feito. Clonei o repositório num diretório novo, sem `.env`, `.venv` nem
`node_modules`, e segui o README à risca. Encontrou **dois defeitos**.

**`pytest` sem `.env` derrubava a suíte inteira.** Não pulava os testes — dava
erro de coleta e nada rodava. `backend/main.py` chama `configuracao()` já no
import, para o `CORSMiddleware`, e `tests/api/` importa a aplicação. Sem
`DATABASE_URL`, `ValidationError` na coleta.

Isso contradizia a frase do README: "os testes que dependem do banco se pulam
sozinhos". Era falsa para quem acabou de clonar — que é exatamente quem lê essa
frase. `tests/api/conftest.py` passou a usar `collect_ignore_glob` quando a
configuração não carrega, e agora **185 testes de domínio passam num clone
limpo**.

**A CLI recusava `100,00`.** A interface web aceitava `1.234,56`; a CLI, um
programa em português, exigia o ponto decimal da máquina. Acrescentado
`perguntar_valor`, espelhando o `paraValorDaApi` do React — a conversão fica na
apresentação, e o domínio continua recebendo valor canônico ([DT-05](01-decisoes-tecnicas.md#dt-05)).

O que o clone limpo **não** cobre: uma máquina sem Docker, sem Supabase CLI e
sem as imagens já em cache. Para isso seria preciso outra máquina.

### RNF-5.5 — `supabase db push` na nuvem

**Bloqueado por credencial.** `supabase login` abre o navegador e exige a conta
do dono do projeto. Não há como fazer por aqui.

O que dava para verificar foi verificado: extraí o schema `auth` real — 35
colunas, depois de o GoTrue aplicar as próprias migrações, que é a forma que a
nuvem tem — para um banco novo, e apliquei as quatro migrações em cima. Todas
passaram, produzindo 3 tabelas, 8 funções, 3 policies, RLS nas três tabelas e a
foreign key para `auth.users`.

Isso responde à pergunta que o requisito faz de fato: *as migrações aplicam num
Supabase de verdade, sem correção manual?* Sim.

Os passos que faltam, quando houver projeto:

```bash
supabase login
supabase link --project-ref <ref-do-projeto>
supabase db push
```

E então preencher o `.env` de produção com os valores de `supabase status`
apontando para a nuvem — lembrando que ali `SUPABASE_URL` usa TLS, e a
aplicação recusa subir sem isso quando `AMBIENTE=producao`.
