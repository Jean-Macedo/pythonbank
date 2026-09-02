> [Índice](README.md) · **Apêndice — Fora de escopo**

# Fora de escopo

Registrado para evitar reabertura. Nada aqui bloqueia o encerramento das seis
fases, e nada aqui deve entrar no meio de uma fase em andamento.

## Não entra nesta versão

| Item | Motivo |
| --- | --- |
| **Pix e integração com o SPB** | Exige participação institucional no arranjo de pagamentos. A transferência interna da F1 cobre o aprendizado técnico equivalente. |
| **Conformidade regulatória e KYC real** | A validação de CPF é de dígito verificador ([RN-0.12](fase-0-dominio.md)), não consulta à Receita. |
| **Multi-moeda e câmbio** | O schema assume BRL implicitamente. Suportar moedas exigiria coluna de moeda no ledger e regras de conversão com data. |
| **Cartões, crédito e investimentos** | Produtos distintos, cada um com seu próprio ledger e ciclo de liquidação. |
| **Aplicativo mobile nativo** | A API REST da F2 já serve um cliente futuro sem alteração. |
| **Operação multi-tenant** | Um banco, uma agência padrão. Multi-agência real exige roteamento e limites por agência. |
| **Agendamento e transferência futura** | Requer job scheduler e um estado "pendente" que o ledger atual não modela. |
| **Extrato em PDF/OFX** | Formatação de relatório, não arquitetura. Sem valor de aprendizado para os objetivos desta versão. |

## Candidatos à v3

> **Estorno saiu desta lista**: foi implementado. O ledger append-only da F1
> sustentava o modelo sem mudança estrutural — o estorno é um lançamento novo,
> de sinal oposto, ligado ao original por `estorno_de`, e o original nunca é
> tocado. Ver [Estorno](07-estorno.md).

Em ordem de proximidade com o que o projeto constrói:

1. **Multi-agência** — `agencia` já é coluna, hoje com valor fixo `0001`.
2. **Limite de saque diário** — política pura, entra em `core/` sem tocar no schema. Bom exercício da fronteira de [DT-05](01-decisoes-tecnicas.md#dt-05).
3. **Conta conjunta** — quebra o `cliente_id` único de `contas` e vira uma tabela de titulares. Mudança de modelagem, não de feature.
4. **Notificação de movimentação** — exige fila ou webhook; primeira dependência de infraestrutura assíncrona do projeto.

## Como usar este documento

Quando surgir uma ideia durante a implementação, ela vai para a lista de
candidatos — não para a fase em andamento. A fase termina pela sua definição de
pronto, não por estar boa o bastante para receber mais uma coisa.
