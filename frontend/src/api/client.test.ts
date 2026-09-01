import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ErroDaApi,
  guardarSessao,
  requisitar,
  sessaoGuardada,
} from './client'
import type { Sessao } from './tipos'

const SESSAO: Sessao = {
  access_token: 'token-de-acesso',
  refresh_token: 'token-de-renovacao',
  expira_em: 3600,
  tipo: 'bearer',
}

function resposta(status: number, corpo?: unknown): Response {
  return new Response(corpo === undefined ? null : JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function comFetch(...respostas: Response[]) {
  const espia = vi.fn()
  respostas.forEach((r) => espia.mockResolvedValueOnce(r))
  vi.stubGlobal('fetch', espia)
  return espia
}

describe('o defeito que este módulo existe para impedir', () => {
  it('resposta 4xx vira erro, não sucesso', async () => {
    // `fetch` não rejeita em 422 — sem checar `response.ok`, um saque recusado
    // seguiria pelo caminho de sucesso e a pessoa acharia que sacou
    comFetch(
      resposta(422, {
        codigo: 'SALDO_INSUFICIENTE',
        mensagem: 'Saldo insuficiente para esta operação.',
      }),
    )

    await expect(requisitar('/api/contas/1/saque')).rejects.toThrow(ErroDaApi)
  })

  it('o erro carrega o código, que é o que decide o quê fazer', async () => {
    comFetch(
      resposta(422, { codigo: 'SALDO_INSUFICIENTE', mensagem: 'Saldo insuficiente.' }),
    )

    await expect(requisitar('/x')).rejects.toMatchObject({
      codigo: 'SALDO_INSUFICIENTE',
      status: 422,
    })
  })

  it('resposta de erro sem corpo reconhecível não vira sucesso', async () => {
    comFetch(new Response('<html>502 Bad Gateway</html>', { status: 502 }))

    await expect(requisitar('/x')).rejects.toMatchObject({
      codigo: 'ERRO_INESPERADO',
      status: 502,
    })
  })
})

describe('token', () => {
  beforeEach(() => guardarSessao(SESSAO))

  it('é injetado nas rotas autenticadas', async () => {
    const espia = comFetch(resposta(200, { contas: [] }))
    await requisitar('/api/contas')

    const cabecalhos = espia.mock.calls[0][1].headers as Record<string, string>
    expect(cabecalhos.Authorization).toBe('Bearer token-de-acesso')
  })

  it('não vai nas rotas públicas', async () => {
    const espia = comFetch(resposta(200, SESSAO))
    await requisitar('/auth/login', {
      metodo: 'POST',
      corpo: { email: 'a@b.c', senha: 'x' },
      autenticada: false,
    })

    const cabecalhos = espia.mock.calls[0][1].headers as Record<string, string>
    expect(cabecalhos.Authorization).toBeUndefined()
  })
})

describe('renovação da sessão', () => {
  beforeEach(() => guardarSessao(SESSAO))

  it('401 dispara uma renovação e repete a requisição', async () => {
    const nova = { ...SESSAO, access_token: 'token-novo' }
    const espia = comFetch(
      resposta(401, { codigo: 'NAO_AUTENTICADO', mensagem: 'Sessão expirada.' }),
      resposta(200, nova),
      resposta(200, { contas: [] }),
    )

    await requisitar('/api/contas')

    expect(espia).toHaveBeenCalledTimes(3)
    expect(sessaoGuardada()?.access_token).toBe('token-novo')
  })

  it('renovação recusada derruba a sessão em vez de insistir', async () => {
    comFetch(
      resposta(401, { codigo: 'NAO_AUTENTICADO', mensagem: 'Sessão expirada.' }),
      resposta(401, { codigo: 'FALHA_DE_AUTENTICACAO', mensagem: 'Inválido.' }),
      resposta(401, { codigo: 'NAO_AUTENTICADO', mensagem: 'Sessão expirada.' }),
    )

    await expect(requisitar('/api/contas')).rejects.toThrow(ErroDaApi)
    expect(sessaoGuardada()).toBeNull()
  })

  it('não entra em laço: renova no máximo uma vez', async () => {
    const espia = comFetch(
      resposta(401, { codigo: 'NAO_AUTENTICADO', mensagem: 'x' }),
      resposta(200, SESSAO),
      resposta(401, { codigo: 'NAO_AUTENTICADO', mensagem: 'x' }),
    )

    await expect(requisitar('/api/contas')).rejects.toThrow()
    expect(espia).toHaveBeenCalledTimes(3) // pedido, renovação, repetição
  })
})

describe('falha de conexão', () => {
  it('é distinguida de erro da API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    try {
      await requisitar('/api/contas')
      expect.unreachable('deveria ter lançado')
    } catch (erro) {
      expect(erro).toBeInstanceOf(ErroDaApi)
      expect((erro as ErroDaApi).ehFalhaDeConexao).toBe(true)
    }
  })
})

describe('armazenamento da sessão', () => {
  it('sobrevive a conteúdo corrompido', () => {
    localStorage.setItem('banco-jean.sessao', 'isto não é json')
    expect(sessaoGuardada()).toBeNull()
  })

  it('204 devolve vazio sem tentar ler corpo', async () => {
    guardarSessao(SESSAO)
    comFetch(new Response(null, { status: 204 }))
    await expect(requisitar('/api/contas/1', { metodo: 'DELETE' })).resolves.toBeUndefined()
  })
})
