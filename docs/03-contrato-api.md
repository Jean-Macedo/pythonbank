> [Índice](README.md) · **03 — Contrato da API**

# Contrato da API

Todo endpoint sob `/api` exige `Authorization: Bearer <jwt>`.

Como um cliente tem várias contas, o `conta_id` aparece **no caminho da rota** —
nunca no corpo — e toda rota que o recebe verifica titularidade antes de agir
([DT-04](01-decisoes-tecnicas.md#dt-04)).

## Autenticação

| Método | Rota | Corpo | Resposta |
| --- | --- | --- | --- |
| `POST` | `/auth/registro` | `nome`, `cpf`, `email`, `telefone`, `data_nascimento`, `senha` | `201` · cliente criado com uma conta corrente inicial |
| `POST` | `/auth/login` | `email`, `senha` | `200` · `access_token`, `refresh_token` |
| `POST` | `/auth/refresh` | `refresh_token` | `200` · `access_token` |

## Cliente

| Método | Rota | Corpo | Resposta |
| --- | --- | --- | --- |
| `GET` | `/api/me` | — | `200` · dados cadastrais do titular |

## Contas

| Método | Rota | Corpo | Resposta |
| --- | --- | --- | --- |
| `GET` | `/api/contas` | — | `200` · lista das contas ativas do titular |
| `POST` | `/api/contas` | `tipo`, `apelido?` | `201` · conta criada com agência, número e saldo zero |
| `GET` | `/api/contas/{conta_id}` | — | `200` · agência, número, tipo, apelido, saldo |
| `PATCH` | `/api/contas/{conta_id}` | `apelido` | `200` · conta atualizada |
| `DELETE` | `/api/contas/{conta_id}` | — | `204` · conta encerrada (exige saldo zero) |

`GET /api/contas` é a rota que a interface carrega primeiro — sem ela o
frontend não sabe sobre qual conta operar.

### Exemplo — `GET /api/contas`

```json
{
  "contas": [
    { "id": 1, "agencia": "0001", "numero": "00100001", "tipo": "corrente",
      "apelido": "Dia a dia", "saldo": "1250.00" },
    { "id": 2, "agencia": "0001", "numero": "00100002", "tipo": "poupanca",
      "apelido": "Reserva",   "saldo": "8400.35" }
  ]
}
```

Saldos como **string** — ver [DT-01](01-decisoes-tecnicas.md#dt-01).

## Movimentação

| Método | Rota | Corpo | Resposta |
| --- | --- | --- | --- |
| `POST` | `/api/contas/{conta_id}/deposito` | `valor` | `201` · `saldo_atual`, `transacao_id` |
| `POST` | `/api/contas/{conta_id}/saque` | `valor` | `201` · `saldo_atual`, `transacao_id` |
| `POST` | `/api/contas/{conta_id}/transferencia` | `valor`, `agencia_destino`, `numero_destino` | `201` · `saldo_atual` |
| `GET` | `/api/contas/{conta_id}/extrato` | `?limite=50&cursor=` | `200` · `transacoes`, `proximo_cursor` |

A transferência identifica o destino por **agência + número**, não por `id`
interno. O cliente não conhece nem deveria adivinhar ids de contas alheias.

### Exemplo — depósito

```http
POST /api/contas/1/deposito
Authorization: Bearer eyJ...
Content-Type: application/json

{ "valor": "100.00" }
```

```json
{ "saldo_atual": "1350.00", "transacao_id": 4821 }
```

Um `conta_id` enviado no corpo é **ignorado**, não obedecido.

### Paginação do extrato

Cursor sobre `(data_hora, id)`, nunca `offset` — o ledger cresce e recebe
inserções durante a navegação. `proximo_cursor` vem `null` na última página.

## Mapeamento de erros

As funções PL/pgSQL levantam exceções com códigos estáveis. O backend traduz
cada um para um HTTP previsível. O frontend decide pelo campo `codigo`, **nunca
interpretando a mensagem em português**.

| Código de domínio | HTTP | Mensagem ao usuário |
| --- | --- | --- |
| `VALOR_INVALIDO` | `422` | O valor precisa ser maior que zero. |
| `SALDO_INSUFICIENTE` | `422` | Saldo insuficiente para esta operação. |
| `CONTA_NAO_ENCONTRADA` | `404` | Conta de destino não encontrada. |
| `CONTAS_IGUAIS` | `422` | Escolha uma conta de destino diferente da de origem. |
| `CONTA_NAO_ENCERRAVEL` | `422` | Só é possível encerrar uma conta com saldo zero. |
| `LIMITE_DE_CONTAS` | `422` | Você atingiu o limite de contas abertas. |
| `APELIDO_DUPLICADO` | `409` | Você já tem uma conta com este apelido. |
| `CPF_DUPLICADO` | `409` | Já existe um cadastro com este CPF. |
| — | `401` | Sua sessão expirou. Entre novamente. |
| — | `404` | Conta não encontrada. |

> **Nota de segurança.** A última linha cobre dois casos que o cliente não pode
> distinguir: a conta não existe, ou existe e pertence a outra pessoa. Ambos
> respondem `404` com a mesma mensagem. Um `403` confirmaria a existência do
> identificador e permitiria enumerar as contas do banco.

### Formato da resposta de erro

```json
{ "codigo": "SALDO_INSUFICIENTE",
  "mensagem": "Saldo insuficiente para esta operação." }
```
