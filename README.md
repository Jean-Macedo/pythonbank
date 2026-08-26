# Banco Jean

Sistema bancário em Python, construído para exercitar Programação Orientada a
Objetos em um domínio onde os erros têm consequência: dinheiro.

O projeto está sendo levado de um script de terminal para uma arquitetura de
serviços com ledger transacional, API autenticada e interface web. O plano
completo está em [`docs/`](docs/).

**Estado atual: Fase 1 concluída** — domínio isolado e persistência transacional
em PostgreSQL, com movimentação atômica e ledger imutável.

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
transferência entre contas e extrato. O estado ainda vive em memória: a CLI é
apresentação sobre o domínio, e ligá-la ao banco é trabalho da Fase 2, quando os
repositórios entram.

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

### Os testes

```bash
pytest                 # suíte completa: 135 unitários + 42 de integração
pytest tests/integracao   # só integração (exige `supabase start`)
pytest --cov           # com relatório de cobertura
ruff check .           # lint
```

Os testes de integração se **pulam sozinhos** quando o banco não está no ar, de
modo que `pytest` continua funcionando em uma máquina sem Docker.

---

## Estrutura

```
core/                 domínio — não conhece banco, HTTP nem terminal
├── cliente.py        dados cadastrais e as contas que o cliente possui
├── conta.py          regras de movimentação e ciclo de vida da conta
├── dinheiro.py       Decimal com duas casas; float é rejeitado, não convertido
├── erros.py          ErroDeDominio e subclasses, cada uma com código estável
└── eventos.py        Transacao — lançamento imutável do ledger

supabase/
├── migrations/       schema e funções PL/pgSQL — o mecanismo de evolução
├── seed.sql          dois clientes, três contas, para desenvolvimento
└── config.toml       serviços ativos do stack local

tests/                177 testes
├── test_*.py         domínio, mais checagens de arquitetura por AST
└── integracao/       contra o PostgreSQL real; pulam sozinhos sem banco

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

---

## Roteiro

| Fase | Entrega | Estado |
| --- | --- | --- |
| [F0](docs/fase-0-dominio.md) | Domínio isolado, `Decimal`, N contas por cliente, testes | **Concluída** |
| [F1](docs/fase-1-persistencia.md) | PostgreSQL via Supabase local, movimentação atômica em PL/pgSQL | **Concluída** |
| [F2](docs/fase-2-api-rest.md) | API REST com FastAPI | A fazer |
| [F3](docs/fase-3-autenticacao.md) | Autenticação, RLS e verificação de titularidade | A fazer |
| [F4](docs/fase-4-interface.md) | Interface web em React | A fazer |
| [F5](docs/fase-5-empacotamento.md) | Docker Compose e implantação | A fazer |

---

## Contribuindo

Nada vai direto para a `main`: todo trabalho nasce em uma branch `feat/` ou
`fix/`, é mergeado com `--no-ff` e a branch é apagada em seguida. O ciclo
completo está em [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Licença

MIT — ver [LICENSE](LICENSE).
