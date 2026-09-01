> [Índice](README.md) · **Fase 4 — Interface web**

# Fase 4 — Interface web

| | |
| --- | --- |
| **Depende de** | **F3** (bloqueante) |
| **Bloqueia** | F5 |
| **Estimativa** | 4–5 dias |
| **Entregável** | SPA em `:5173` consumindo a API autenticada |

React consumindo a API autenticada. A regra central: **o frontend valida para
dar feedback rápido, nunca para autorizar.** Toda validação daqui é duplicada no
backend, e é a do backend que vale.

## Consequência de várias contas por cliente

A interface ganha um conceito que não existia no plano original: **a conta
selecionada**. O fluxo de abertura passa a ser:

```
login → GET /api/contas → seletor de conta → painel da conta escolhida
```

Nenhuma tela opera sobre "a conta do usuário" no singular. A conta ativa vive
no estado global e vai no caminho de toda requisição de movimentação.

## Componentes

| Componente | Responsabilidade |
| --- | --- |
| `App.jsx` | Rotas, sessão, conta selecionada e guarda de autenticação |
| `LoginForm.jsx` | Entrada e cadastro; armazena o token e o renova |
| `Header.jsx` | Titular e ação de sair |
| `SeletorDeConta.jsx` | Lista as contas do titular, troca a ativa, abre conta nova |
| `SaldoPanel.jsx` | Saldo da conta ativa, com estado de carregamento e de erro |
| `TransacaoForm.jsx` | Depositar, sacar e transferir na conta ativa |
| `ExtratoList.jsx` | Histórico paginado, entradas e saídas visualmente distintas |
| `api/client.js` | Wrapper único de `fetch`: injeta o token, checa `response.ok`, normaliza erro |

## Requisitos

| ID | Requisito | Prio |
| --- | --- | --- |
| **RF-4.1** | Toda chamada verifica `response.ok` **antes** de tratar o corpo como sucesso. Ver a [nota abaixo](#o-bug-do-exemplo-original). | P0 |
| **RF-4.2** | Nenhuma requisição é montada fora de `api/client.js`. Token, tratamento de `401` e normalização de erro existem em um lugar só. | P0 |
| **RN-4.3** | Valores formatados com `Intl.NumberFormat('pt-BR', { style:'currency', currency:'BRL' })`. **Nunca somados em JavaScript** — o saldo exibido vem sempre da resposta da API. ([DT-01](01-decisoes-tecnicas.md#dt-01)) | P0 |
| **RF-4.4** | Botão de envio bloqueado enquanto a requisição está em voo, evitando duplo débito por duplo clique. | P0 |
| **RF-4.5** | Transferência entre contas do próprio titular oferece as outras contas em um seletor, além do campo livre de agência e número. É o caso mais frequente com N contas. | P1 |
| **RF-4.6** | Erro exibido no contexto do formulário, escolhido pelo campo `codigo` da resposta — nunca `alert()`, nunca comparando a mensagem em português. | P1 |
| **RF-4.7** | Saldo e extrato revalidados após cada transação bem-sucedida, na conta de origem **e** na de destino se ambas forem do titular. | P1 |
| **RF-4.8** | `401` em qualquer resposta tenta o refresh uma vez; falhando, limpa a sessão e redireciona ao login. | P1 |
| **RNF-4.9** | URL da API por variável de ambiente (`VITE_API_URL`), não fixa no código. | P1 |
| **RNF-4.10** | Navegação por teclado alcança todos os controles, com foco visível. Valores monetários com `font-variant-numeric: tabular-nums`. | P2 |

<a id="o-bug-do-exemplo-original"></a>
## O bug do exemplo original

O `fetch` do guia anterior não checava `response.ok`:

```js
// ERRADO — o do guia original
const response = await fetch(url, { ... });
const data = await response.json();
alert(data.mensagem);          // 400 cai aqui e mostra "undefined"
```

`fetch` só rejeita a promise em falha de rede. Um `HTTPException(400)` do
FastAPI é uma resposta HTTP bem-sucedida do ponto de vista do `fetch` — não cai
no `catch`, segue pelo caminho de sucesso, e o usuário vê uma falha silenciosa
e presume que a operação funcionou. **Em um banco, presumir que um saque
funcionou é o pior resultado possível.**

```js
// CORRETO — em api/client.js, uma vez para todas as chamadas
const resposta = await fetch(url, opcoes);
const corpo = await resposta.json().catch(() => ({}));
if (!resposta.ok) {
  throw new ErroDaApi(corpo.codigo ?? "ERRO_DESCONHECIDO", corpo.mensagem, resposta.status);
}
return corpo;
```

## Definição de pronto

- [ ] Saque acima do saldo mostra a mensagem do backend no formulário, não uma tela quebrada nem um sucesso falso.
- [ ] Duplo clique em "Depositar" gera uma transação, não duas.
- [ ] Trocar a conta ativa recarrega saldo e extrato da conta correta.
- [ ] Transferência entre duas contas do titular atualiza as duas na tela.
- [ ] Token expirado renova em silêncio ou redireciona ao login — nunca falha sem explicação.
- [ ] Nenhum `fetch` fora de `api/client.js`.
- [ ] Nenhuma aritmética com valores monetários no código JavaScript.
- [ ] Navegação por teclado alcança todos os controles com foco visível.

## Riscos da fase

**Precisão decimal se perde na borda.** `JSON.parse` converte número em `float`
de 64 bits. Os valores chegam como string exatamente por isso, e a única
proteção real é a disciplina de nunca fazer conta com eles no cliente — o saldo
exibido é sempre o que a API devolveu, nunca um cálculo local.

---

## Emendas aplicadas na execução

### TypeScript no lugar de `.jsx`

O PRD previa JavaScript. Com TypeScript, `Dinheiro` é um alias de `string` e o
compilador **recusa** `conta.saldo + 100` antes de o código existir — a defesa da
[DT-01](01-decisoes-tecnicas.md#dt-01) na borda deixa de depender de disciplina.

### Um tipo próprio para erro de validação local

O componente `Erro` começou exibindo mensagem só de `ErroDaApi`. Consequência
descoberta por teste: as validações do próprio formulário — "informe um valor
maior que zero", justamente a mensagem mais útil — viravam "algo deu errado".

Exibir a mensagem de qualquer `Error` resolveria, mas faria o texto de um
`TypeError` de defeito interno aparecer na tela do usuário. A saída foi
`ErroDeValidacao`, um tipo próprio: o componente sabe exatamente quais mensagens
pode mostrar.

### `erasableSyntaxOnly`

O template do Vite liga essa opção, que proíbe propriedades declaradas no
construtor (`constructor(readonly x: string)`). Os campos de `ErroDaApi` são
declarados explicitamente por isso.

### O painel de saldo tem nome acessível

`aria-label="Saldo da conta ativa"`. Surgiu de um teste que falhava por encontrar
o mesmo valor duas vezes — o saldo aparece no seletor de contas **e** no painel.
Em vez de tornar a consulta frágil, o componente ganhou identidade, o que também
o torna navegável por leitor de tela.

### Testes de componente com backend dublê, contrato verificado no real

`vitest` com Testing Library cobre o comportamento da interface; as operações da
API são substituídas por dublês. Isso não verificaria que o contrato está certo,
então o formato foi conferido contra a API de verdade: `saldo` chega como
`String`, e o CORS libera `http://localhost:5173`.
