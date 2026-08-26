# Fluxo de trabalho

Nada é commitado diretamente na `main`. Todo trabalho nasce em uma branch
temporária, é mergeado com `--no-ff` e a branch é apagada em seguida.

## Prefixos de branch

| Prefixo | Para quê | Exemplo |
| --- | --- | --- |
| `feat/` | Funcionalidade nova, uma fase do PRD | `feat/persistencia-supabase` |
| `fix/` | Correção rápida de erro no código | `fix/saldo-negativo-no-extrato` |
| `docs/` | Só documentação | `docs/fluxo-de-branches` |
| `chore/` | Ferramental, CI, dependências | `chore/github-actions` |

Nome em minúsculas, palavras separadas por hífen, descrevendo **o que muda** —
não `fix/bug` nem `feat/nova-feature`.

## O ciclo

```bash
# 1. sempre partindo da main atualizada
git checkout main
git pull

# 2. branch temporária
git checkout -b fix/saldo-negativo-no-extrato

# 3. trabalhe e commite normalmente
git add -A
git commit -m "fix: extrato exibia saldo negativo após estorno"

# 4. publique a branch (backup e visibilidade enquanto o trabalho corre)
git push -u origin fix/saldo-negativo-no-extrato

# 5. mergeie na main preservando a estrutura
git checkout main
git merge --no-ff fix/saldo-negativo-no-extrato
git push

# 6. apague a branch nos dois lados
git branch -d fix/saldo-negativo-no-extrato
git push origin --delete fix/saldo-negativo-no-extrato
```

O passo 5 usa `--no-ff` de propósito: sem ele, apagar a branch no passo 6 apaga
também a informação de que ela existiu. Com o commit de merge, o histórico
continua mostrando quais commits pertenciam a qual trabalho.

```
*   8f2a1  Merge branch 'feat/persistencia-supabase'
|\
| * c4d9e  test: concorrência em depósito simultâneo
| * a1b3f  feat: funções PL/pgSQL de movimentação
|/
*   361c3  feat: Fase 0 — domínio isolado
```

## Configuração local

O `--no-ff` já é o padrão deste repositório, mas a configuração vive em
`.git/config`, que **não é versionado**. Depois de clonar em uma máquina nova:

```bash
git config merge.ff false    # todo merge cria commit de merge
git config pull.ff only      # pull nunca inventa merge; falha e você decide
```

## Antes de mergear na main

A `main` deve estar sempre executável. Antes do passo 5:

```bash
pytest          # 135 testes
ruff check .    # lint
```

Se algum falhar, o conserto é na branch — não na `main` depois do merge.

## Mensagens de commit

Prefixo do tipo, dois pontos, descrição no imperativo e em minúsculas:

```
feat: funções PL/pgSQL de movimentação atômica
fix: extrato exibia saldo negativo após estorno
docs: contrato da API com rotas de transferência
test: concorrência em depósito simultâneo
chore: GitHub Actions rodando pytest e ruff
```

Corpo opcional, separado por linha em branco, explicando **por que** — o que
mudou o `diff` já conta.

## Uma branch, um assunto

Se no meio de uma correção você achar outra coisa para arrumar, ela vira outra
branch. Branch que acumula assuntos não tem como ser revertida sem levar junto o
que não devia.
