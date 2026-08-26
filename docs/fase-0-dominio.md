> [Índice](README.md) · **Fase 0 — Fundação do domínio**

# Fase 0 — Fundação do domínio

| | |
| --- | --- |
| **Depende de** | nada |
| **Bloqueia** | F1, F2 |
| **Estimativa** | 1–2 dias |
| **Entregável** | pacote `core/` testado, CLI antigo rodando sobre ele |

Antes de tocar em banco de dados. Consolidar o que já existe evita carregar os
defeitos atuais para dentro da nova arquitetura, onde custam muito mais para
corrigir.

## Correção dos defeitos atuais

| ID | Requisito | Prio |
| --- | --- | --- |
| **RF-0.1** | Corrigir a property `idade` em `cliente.py`. Falta parêntese: a expressão é hoje `(int - int - tupla) < tupla` e levanta `TypeError` em toda chamada. | P0 |
| **RF-0.2** | Substituir a cadeia `if / if / if / elif / else` do menu em `interface.py`. As opções 1, 2 e 3 caem no `else` final e imprimem "Opção inválida" mesmo tendo sido processadas. | P0 |
| **RF-0.3** | A opção `0` não interrompe o laço — adicionar `break`. E `nome` na despedida é `NameError` se nenhum cliente foi cadastrado. | P0 |
| **RF-0.4** | Corrigir o `else` do `try` no saque, que anuncia "nenhuma conta cadastrada" justamente quando a operação foi bem-sucedida. | P0 |
| **RF-0.5** | Envolver `int(input(...))` do menu em tratamento de erro — digitar uma letra derruba o programa. | P0 |
| **RN-0.6** | Separar o erro de data futura do erro de formato. O `except ValueError` do setter engole o próprio `raise` e devolve "Formato inválido", mascarando o motivo real. | P1 |

## Modelagem do domínio

| ID | Requisito | Prio |
| --- | --- | --- |
| **RN-0.7** | Introduzir `Decimal` em toda a camada de domínio. Conversão de entrada com `Decimal(str(valor))` e `quantize(Decimal("0.01"))`. Nenhum `float` sobrevive. ([DT-01](01-decisoes-tecnicas.md#dt-01)) | P0 |
| **RF-0.8** | `Cliente` passa a agregar **N contas**: `cliente.contas` é uma coleção e `cliente.abrir_conta(tipo, apelido)` é o ponto de criação. | P0 |
| **RN-0.9** | Política de contas no domínio: máximo de **5 contas ativas** por cliente (`LIMITE_DE_CONTAS`) e apelido único dentro do cliente (`APELIDO_DUPLICADO`). Regra de política, não de integridade — vive no Python. ([DT-05](01-decisoes-tecnicas.md#dt-05)) | P1 |
| **RN-0.10** | `Conta.encerrar()` só é permitido com saldo zero (`CONTA_NAO_ENCERRAVEL`). | P1 |
| **RF-0.11** | `Conta` deixa de guardar histórico em lista de strings formatadas e passa a expor eventos estruturados (`tipo`, `valor`, `saldo_apos`, `data_hora`). Formatação é responsabilidade da apresentação. | P1 |
| **RN-0.12** | Validar CPF por **dígitos verificadores**, não apenas por formato. Rejeitar também os repetidos (`11111111111`). | P1 |
| **RF-0.13** | Criar `core/erros.py` com `ErroDeDominio` e subclasses portando os códigos da [tabela de erros](03-contrato-api.md#mapeamento-de-erros). Nenhum `raise ValueError` genérico permanece no domínio. | P0 |

## Estrutura alvo

```
core/
├── __init__.py
├── cliente.py       # Cliente, agrega N contas
├── conta.py         # Conta, TipoConta
├── dinheiro.py      # conversão e quantização de Decimal
├── erros.py         # ErroDeDominio e subclasses com código
└── eventos.py       # Transacao como evento estruturado
tests/
├── test_cliente.py
├── test_conta.py
└── test_dinheiro.py
interface.py         # CLI, consome core/ e não valida nada por conta própria
```

## Testes obrigatórios

| ID | Requisito | Prio |
| --- | --- | --- |
| **RNF-0.14** | Suíte `pytest` cobrindo: depósito, saque, saldo insuficiente, valor zero, valor negativo, encerramento com saldo, limite de contas, apelido duplicado e todas as validações de `Cliente`. | P0 |
| **RNF-0.15** | Teste de precisão: somar `"0.10"` três vezes resulta em `Decimal("0.30")` exato — o teste que falha se alguém reintroduzir `float`. | P0 |
| **RNF-0.16** | `pyproject.toml` com `pytest`, `pytest-cov` e `ruff` configurados. | P2 |

## Definição de pronto

- [ ] `pytest` passa com cobertura ≥ 90% em `core/` ([CA-06](00-visao-e-escopo.md#critérios-de-aceite-globais)).
- [ ] `grep -rn "float(" core/` não retorna nada ([CA-01](00-visao-e-escopo.md#critérios-de-aceite-globais)).
- [ ] `grep -rnE "supabase|fastapi|input\(|print\(" core/` não retorna nada.
- [ ] Todo erro levantado pelo domínio é uma subclasse de `ErroDeDominio` com `codigo` preenchido.
- [ ] O CLI continua funcionando sobre o domínio refatorado, agora com seleção de conta — é o teste de fumaça da separação.
- [ ] `ruff check` limpo.

## Riscos da fase

O CLI é descartado nas fases seguintes, então há tentação de não mantê-lo
funcionando. Mantenha: enquanto ele roda sobre `core/` sem importar nada de
infraestrutura, a separação de [DT-05](01-decisoes-tecnicas.md#dt-05) está
comprovada na prática, e não apenas na intenção.
