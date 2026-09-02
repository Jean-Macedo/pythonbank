# Banco Jean — Documentação de Produto

PRD v2.1 · Revisão 26/08/2026 · Autor: Jean

Evolução do sistema bancário CLI em POO para uma arquitetura de serviços com
ledger transacional, API autenticada e interface web.

---

## Como usar estes documentos

Os quatro primeiros arquivos são **transversais**: valem para todas as fases e
devem ser lidos antes de começar qualquer implementação. Os arquivos `fase-*`
são **unidades de trabalho fechadas** — cada um tem requisitos numerados,
critérios de aceite e definição de pronto verificável.

Trabalhe uma fase por vez. Não abra a próxima antes que a definição de pronto
da anterior esteja inteiramente marcada.

## Índice

### Transversal

| Documento | Conteúdo |
| --- | --- |
| [00 — Visão e escopo](00-visao-e-escopo.md) | Problema, objetivos, critérios de aceite globais |
| [01 — Decisões técnicas](01-decisoes-tecnicas.md) | As 6 restrições que valem para todas as fases |
| [02 — Modelo de dados](02-modelo-de-dados.md) | DDL, funções PL/pgSQL, reconciliação |
| [03 — Contrato da API](03-contrato-api.md) | Endpoints, corpos, mapeamento de erros |

### Fases

| Fase | Documento | Depende de | Estimativa |
| --- | --- | --- | --- |
| F0 | [Fundação do domínio](fase-0-dominio.md) | — | 1–2 dias |
| F1 | [Persistência transacional](fase-1-persistencia.md) | F0 | 3–4 dias |
| F2 | [API REST](fase-2-api-rest.md) | F0, F1 | 3–4 dias |
| F3 | [Autenticação e autorização](fase-3-autenticacao.md) | F1, F2 | 2–3 dias |
| F4 | [Interface web](fase-4-interface.md) | **F3** | 4–5 dias |
| F5 | [Empacotamento](fase-5-empacotamento.md) | F2, F4 | 1–2 dias |

**F3 bloqueia F4.** Um frontend escrito contra endpoints sem autenticação
embute suposições que precisam ser desfeitas depois.

### Depois das fases

| Documento | Conteúdo |
| --- | --- |
| [07 — Estorno](07-estorno.md) | Lançamento de sinal oposto; o original permanece |

### Apêndices

- [Riscos](riscos.md)
- [Fora de escopo](fora-de-escopo.md)

## Convenção de identificadores

| Prefixo | Significado |
| --- | --- |
| `DT-nn` | Decisão técnica — restrição transversal |
| `CA-nn` | Critério de aceite global |
| `RF-f.n` | Requisito funcional da fase `f` |
| `RN-f.n` | Regra de negócio da fase `f` |
| `RNF-f.n` | Requisito não-funcional da fase `f` |

Prioridades: **P0** bloqueia a fase · **P1** entra na fase · **P2** pode escorregar.

## Estado atual do repositório

O código na raiz (`cliente.py`, `conta.py`, `interface.py`) é o protótipo CLI
que a Fase 0 consolida. Ele permanece funcionando durante toda a F0 como teste
de fumaça da separação entre domínio e apresentação.
