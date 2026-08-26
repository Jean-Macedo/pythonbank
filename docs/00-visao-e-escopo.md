> [Índice](README.md) · **00 — Visão e escopo**

# Visão e escopo

## Problema

O sistema atual é um script de terminal com três classes e estado em memória:
fechar o programa apaga a conta. Além da ausência de persistência, o protótipo
carrega quatro defeitos que impedem qualquer uso além da demonstração.

| Defeito | Consequência | Endereçado em |
| --- | --- | --- |
| Dinheiro em ponto flutuante | Saldo diverge de centavos ao acumular transações | [DT-01](01-decisoes-tecnicas.md#dt-01) · F0 |
| Operações não atômicas | Saldo e histórico podem divergir permanentemente | [DT-02](01-decisoes-tecnicas.md#dt-02) · F1 |
| Nenhuma noção de identidade | Qualquer chamador opera qualquer conta | [DT-04](01-decisoes-tecnicas.md#dt-04) · F3 |
| Bugs de fluxo no menu | `TypeError` em `idade`, opções válidas rejeitadas | F0 |

## Objetivos

1. Toda movimentação financeira é **atômica e auditável** — saldo e ledger
   nunca divergem.
2. Valores monetários usam **precisão decimal exata** de ponta a ponta.
3. Um cliente pode manter **várias contas** e só enxerga e movimenta as
   próprias, garantido em duas camadas independentes.
4. A lógica de negócio vive em classes Python **testáveis sem banco e sem
   HTTP**.
5. O ambiente de desenvolvimento inteiro sobe **local, com um comando**, sem
   depender da nuvem.

## Não-objetivos

Esta versão não trata de multi-moeda, cartões, empréstimos, rendimento, Pix,
conformidade regulatória, aplicativo nativo ou operação multi-tenant.
Detalhamento e justificativa em [Fora de escopo](fora-de-escopo.md).

## Critérios de aceite globais

Valem para o projeto inteiro. Nenhuma fase é considerada pronta se quebrar um
destes.

| ID | Critério | Verificação |
| --- | --- | --- |
| **CA-01** | Nenhum caminho de código representa dinheiro como `float` | Busca estática + revisão |
| **CA-02** | Para toda conta, a soma do ledger é idêntica ao saldo armazenado | [Query de reconciliação](02-modelo-de-dados.md#reconciliação) |
| **CA-03** | Requisição sem token válido não lê nem move nada | Teste de integração |
| **CA-04** | Cliente A não acessa conta do cliente B por nenhuma rota | Teste de integração |
| **CA-05** | Nenhum segredo versionado no Git | `.env` em `.gitignore` |
| **CA-06** | Cobertura de testes do módulo de domínio ≥ 90% | `pytest --cov=core` |

## Glossário

| Termo | Significado neste projeto |
| --- | --- |
| **Ledger** | A tabela `transacoes`. Registro imutável e append-only de toda movimentação. É a fonte da verdade. |
| **Saldo** | Coluna `contas.saldo`. Cache do ledger, mantido na mesma transação — nunca calculado à parte. |
| **Domínio** | Pacote `core/`. Classes que conhecem regras de negócio e não conhecem banco, HTTP nem terminal. |
| **Repositório** | Pacote `infra/`. Traduz entre objetos de domínio e persistência. É o único que importa `supabase`. |
| **Titularidade** | Vínculo `conta.cliente_id → cliente.auth_user_id`. Verificada em toda rota que recebe um `conta_id`. |
