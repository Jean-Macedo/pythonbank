# Banco Jean

Sistema bancário em Python, construído para exercitar Programação Orientada a
Objetos em um domínio onde os erros têm consequência: dinheiro.

O projeto está sendo levado de um script de terminal para uma arquitetura de
serviços com ledger transacional, API autenticada e interface web. O plano
completo está em [`docs/`](docs/).

**Estado atual: Fase 4 concluída** — domínio isolado, persistência transacional,
API autenticada por JWT e interface web em React.

---

## Como rodar

Requer Python 3.11 ou superior.

```bash
git clone https://github.com/Jean-Macedo/pythonbank.git
cd pythonbank

python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# .venv\Scripts\activate           # Windows (PowerShell)
# source .venv/bin/activate        # Linux e macOS

pip install -e ".[dev]"
```

### A aplicação

```bash
python interface.py
```

Um menu de terminal com cadastro, abertura de contas, depósito, saque,
transferência entre contas e extrato. O estado vive em memória: a CLI existe
como prova de que o domínio funciona sem infraestrutura nenhuma, e é o que os
testes de arquitetura verificam. Quem fala com o banco é a API, e quem o usuário
vê é a interface web.

### O banco local

Requer [Supabase CLI](https://supabase.com/docs/guides/local-development) e Docker.

```bash
supabase start         # sobe PostgreSQL, Auth, REST e Studio
supabase db reset      # recria o banco do zero: migrações + seed
supabase stop
```

Studio em `http://127.0.0.1:54323`, banco em `postgresql://postgres:postgres@127.0.0.1:54322/postgres`.

> **Serviços desligados de propósito.** `storage`, `realtime`, `edge_runtime` e
> `analytics` estão com `enabled = false` no `config.toml`. Os três primeiros
> segfaltam (`exit 139`) em Windows com WSL2 e derrubam o `supabase start`
> inteiro; nenhum é usado por este projeto. Se você precisar de algum, reative e
> esteja pronto para investigar.

### A API

Com o banco no ar e o `.env` preenchido (`cp .env.example .env`):

```bash
uvicorn backend.main:app --reload
```

Swagger em `http://127.0.0.1:8000/docs`.

Autenticação por JWT do Supabase. Para experimentar:

```bash
# o cadastro já devolve o token
cat > cadastro.json <<'JSON'
{"nome": "Fulano",
 "cpf": "529.982.247-25",
 "email": "f@exemplo.com",
 "telefone": "11987654321",
 "data_nascimento": "10/03/1995",
 "senha": "uma-senha-longa"}
JSON

curl -X POST localhost:8000/auth/registro -H 'Content-Type: application/json' -d @cadastro.json

# e o token abre as rotas autenticadas
curl localhost:8000/api/contas -H "Authorization: Bearer <access_token>"
```

> **O token é ES256**, assinado com chave assimétrica. O `JWT_SECRET` que aparece
> no `supabase status` não valida nada — é resquício do esquema simétrico antigo.
> A validação usa o JWKS em `/auth/v1/.well-known/jwks.json`.

### A interface

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Requer a API no ar. Cadastro, login, várias contas, depósito, saque,
transferência e extrato paginado.

### Os testes

```bash
pytest                   # backend: 283 testes
pytest tests/integracao  # banco (exige `supabase start`)
pytest tests/api         # HTTP ponta a ponta (exige `supabase start`)
pytest --cov             # com relatório de cobertura
ruff check .             # lint

cd frontend
npx vitest run           # frontend: 50 testes
npx tsc --noEmit         # checagem de tipos
```

Os testes que dependem do banco se **pulam sozinhos** quando ele não está no ar,
de modo que `pytest` continua funcionando em uma máquina sem Docker.

> **Os testes escrevem no banco de desenvolvimento.** É consequência de haver um
> banco local só ([DT-06](docs/01-decisoes-tecnicas.md#dt-06)). `contas` e
> `transacoes` são truncadas a cada teste, então quem estiver com a aplicação
> aberta perde as contas que criou — o cadastro sobrevive. `supabase db reset`
> devolve tudo ao estado do seed.

---

## Estrutura

```
backend/
├── core/             domínio — não conhece banco, HTTP nem terminal
│   ├── cliente.py    dados cadastrais e as contas que o cliente possui
│   ├── conta.py      regras de movimentação e ciclo de vida da conta
│   ├── dinheiro.py   Decimal com duas casas; float é rejeitado, não convertido
│   ├── erros.py      ErroDeDominio e subclasses, cada uma com código estável
│   └── eventos.py    Transacao — lançamento imutável do ledger
├── api/              rotas: só transporte, nenhuma regra de negócio
│   ├── auth.py       cadastro, entrada e renovação de sessão
│   └── deps.py       validação de JWT e verificação de titularidade
├── schemas/          contrato HTTP em Pydantic; dinheiro sai como string
├── infra/            o único lugar que fala SQL e com o GoTrue
├── config.py         variáveis de ambiente; falha ao subir se faltarem
└── main.py           app, CORS e tradução de erro para status

supabase/
├── migrations/       schema e funções PL/pgSQL — o mecanismo de evolução
├── seed.sql          dois clientes, três contas, para desenvolvimento
└── config.toml       serviços ativos do stack local

tests/                283 testes
├── test_*.py         domínio, mais checagens de arquitetura por AST
├── integracao/       contra o PostgreSQL real
└── api/              HTTP ponta a ponta: titularidade por rota, JWT e RLS

frontend/
├── src/api/          tipos do contrato e o único lugar que fala HTTP
├── src/componentes/  React, um arquivo por peça da tela
├── src/dinheiro.ts   formatação pt-BR; nunca faz conta
└── src/estilos/      tokens de cor e espaçamento, CSS próprio

interface.py          CLI — lê, delega ao domínio, formata. Não valida nada.
docs/                 PRD: fases, decisões técnicas, modelo de dados, API
```

A separação entre `core/` e o resto não é organizacional, é a premissa do
projeto: enquanto o domínio não importar infraestrutura, a lógica de negócio
sobrevive à troca de qualquer camada em volta. Isso é verificado por testes em
[`tests/test_arquitetura.py`](tests/test_arquitetura.py), não por convenção.

---

## Decisões que moldam o código

Todas detalhadas em [`docs/01-decisoes-tecnicas.md`](docs/01-decisoes-tecnicas.md).

| | |
| --- | --- |
| **Dinheiro é `Decimal`** | `float` é rejeitado com `TypeError`, não convertido. Aceitar `0.1` silenciosamente reintroduz o erro que o módulo existe para evitar. |
| **O ledger é a verdade** | O saldo é cache do histórico, mantido na mesma transação. Uma view de reconciliação prova que os dois nunca divergem. |
| **O domínio não conhece o banco** | O SQL impõe integridade; o Python impõe política. A fronteira é explícita. |
| **Movimentação é atômica** | Depósito, saque e transferência acontecem dentro de funções PL/pgSQL. Nada de ler o saldo, calcular em Python e regravar. |
| **Erro tem código** | Nenhum `ValueError` anônimo. Cada falha de regra carrega um código estável que a apresentação consulta — nunca a mensagem em português. |
| **A conta vem da URL, o dono vem do token** | Toda rota com `conta_id` verifica titularidade num único lugar. Conta alheia responde 404, nunca 403 — um 403 permitiria enumerar as contas do banco. |
| **A RLS protege o banco, não a API** | O backend conecta como dono e ignora RLS. Ela cobre o acesso direto via PostgREST; contra bug de roteamento quem cobre é o teste por rota. Duas camadas, caminhos diferentes. |
| **Dinheiro é `string` no frontend** | `Dinheiro = string` em TypeScript. O compilador recusa `conta.saldo + 100`, e o saldo exibido é sempre o que a API devolveu — nunca calculado na tela. |

---

## Roteiro

| Fase | Entrega | Estado |
| --- | --- | --- |
| [F0](docs/fase-0-dominio.md) | Domínio isolado, `Decimal`, N contas por cliente, testes | **Concluída** |
| [F1](docs/fase-1-persistencia.md) | PostgreSQL via Supabase local, movimentação atômica em PL/pgSQL | **Concluída** |
| [F2](docs/fase-2-api-rest.md) | API REST com FastAPI | **Concluída** |
| [F3](docs/fase-3-autenticacao.md) | Autenticação, RLS e verificação de titularidade | **Concluída** |
| [F4](docs/fase-4-interface.md) | Interface web em React | **Concluída** |
| [F5](docs/fase-5-empacotamento.md) | Docker Compose e implantação | A fazer |

---

## Contribuindo

Nada vai direto para a `main`: todo trabalho nasce em uma branch `feat/` ou
`fix/`, é mergeado com `--no-ff` e a branch é apagada em seguida. O ciclo
completo está em [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Licença

MIT — ver [LICENSE](LICENSE).
