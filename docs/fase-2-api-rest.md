> [Índice](README.md) · **Fase 2 — API REST**

# Fase 2 — API REST

| | |
| --- | --- |
| **Depende de** | F0, F1 |
| **Bloqueia** | F3, F5 |
| **Estimativa** | 3–4 dias |
| **Entregável** | backend em `:8000` com Swagger funcional |

O FastAPI é uma casca de transporte: recebe HTTP, delega ao domínio, persiste
via repositório, traduz erro para status. **Nenhuma regra de negócio nova nasce
aqui.**

## Estrutura de diretórios

```
backend/
├── main.py                  # app, middlewares, inclusão de routers
├── config.py                # Settings via pydantic-settings, lê .env
├── api/
│   ├── deps.py              # get_cliente_atual(), get_conta_do_cliente()
│   ├── auth.py              # registro, login, refresh
│   ├── contas.py            # listar, abrir, detalhar, renomear, encerrar
│   ├── movimentacao.py      # depósito, saque, transferência
│   └── extrato.py
├── schemas/                 # Pydantic — contrato HTTP, não domínio
├── core/                    # domínio puro da F0, sem I/O  (movido para cá)
├── infra/
│   ├── database.py          # cliente Supabase (service_role)
│   └── repositorios.py      # traduz domínio ↔ RPC/tabelas
├── tests/
└── requirements.txt

supabase/migrations/         # permanece na raiz do repositório
```

`core/` é movido para dentro de `backend/` sem alteração de conteúdo. Se algum
teste da F0 quebrar nessa mudança, havia acoplamento escondido.

## Requisitos

| ID | Requisito | Prio |
| --- | --- | --- |
| **RF-2.1** | Implementar todos os endpoints do [Contrato da API](03-contrato-api.md). | P0 |
| **RNF-2.2** | Habilitar `CORSMiddleware` com origem explícita. Sem isso o React é bloqueado pelo navegador na primeira requisição — não é opcional. | P0 |
| **RN-2.3** | Schemas Pydantic usam `condecimal(gt=0, max_digits=15, decimal_places=2)`. A serialização emite valores como **string** para não perder precisão no JSON. ([DT-01](01-decisoes-tecnicas.md#dt-01)) | P0 |
| **RF-2.4** | `exception_handler` global converte `ErroDeDominio` no status correto e devolve `{ "codigo": ..., "mensagem": ... }`. Nenhum handler traduz erro por conta própria. | P0 |
| **RN-2.5** | Dependência `get_conta_do_cliente(conta_id)` resolve a conta **e** verifica titularidade em um único lugar. Toda rota com `{conta_id}` a usa. Conta alheia responde `404`, nunca `403`. ([DT-04](01-decisoes-tecnicas.md#dt-04)) | P0 |
| **RN-2.6** | O repositório chama as funções RPC da F1 — nunca `update` direto em `contas` ou `insert` direto em `transacoes`. | P0 |
| **RNF-2.7** | Credenciais lidas de variáveis de ambiente via `pydantic-settings`. A aplicação **falha ao subir** se faltarem, em vez de rodar com valor vazio. | P0 |
| **RF-2.8** | Extrato paginado por cursor sobre `(data_hora, id)`. Nunca retorna a tabela inteira, nunca usa `offset`. | P1 |
| **RF-2.9** | Endpoint `/health` sem autenticação, usado pelo healthcheck do Docker na F5. | P1 |
| **RNF-2.10** | Testes de integração com `TestClient` cobrindo o caminho feliz e **cada código** da tabela de erros. | P1 |

## Referência — endpoint de depósito

O formato correto, contrastando com o exemplo do guia original:

```python
@router.post("/{conta_id}/deposito", status_code=201,
             response_model=ResultadoTransacao)
def depositar(
    entrada: ValorIn,                              # apenas { "valor": "100.00" }
    conta: Conta = Depends(get_conta_do_cliente),  # resolve + verifica dono
    repo: ContaRepo = Depends(get_conta_repo),
):
    conta.validar_deposito(entrada.valor)          # política, no domínio
    return repo.depositar(conta.id, entrada.valor) # RPC atômica (DT-02)
```

Três coisas que o exemplo original fazia e este não faz: ler o `conta_id` do
corpo, montar o `insert` e o `update` à mão, e decidir o status HTTP dentro do
handler.

## Referência — a dependência de titularidade

```python
def get_conta_do_cliente(
    conta_id: int,
    cliente: Cliente = Depends(get_cliente_atual),
    repo: ContaRepo = Depends(get_conta_repo),
) -> Conta:
    conta = repo.buscar(conta_id)
    # inexistente e alheia respondem igual: 403 confirmaria a existência do id
    if conta is None or conta.cliente_id != cliente.id or not conta.ativa:
        raise ContaNaoEncontrada()
    return conta
```

## Definição de pronto

- [ ] `/docs` abre e todos os endpoints executam pelo Swagger.
- [ ] Requisição com `conta_id` extra no corpo é ignorada, não obedecida.
- [ ] Cada código da [tabela de erros](03-contrato-api.md#mapeamento-de-erros) tem um teste que confirma o status HTTP.
- [ ] Depósito de `"0.10"` três vezes resulta em saldo `"0.30"` exato ([CA-01](00-visao-e-escopo.md#critérios-de-aceite-globais)).
- [ ] Subir a aplicação sem `SUPABASE_URL` falha imediatamente com mensagem clara.
- [ ] `grep -rn "supabase" core/` continua vazio — a F2 não vazou infraestrutura para o domínio.
- [ ] **Revisão da fronteira SQL/Python** ([DT-05](01-decisoes-tecnicas.md#dt-05)): percorrer as funções PL/pgSQL e confirmar que nenhuma política de negócio migrou para lá.

## Riscos da fase

**Rota nova esquecendo a verificação de titularidade.** É o modo de falha mais
provável do projeto inteiro. Mitigação: a verificação existe em um único lugar
(`get_conta_do_cliente`) e a F3 adiciona um teste que percorre **todas** as
rotas com `{conta_id}` tentando acessar conta alheia.
