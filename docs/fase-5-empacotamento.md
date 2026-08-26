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
