import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ErroDaApi } from '../api/client'
import * as operacoes from '../api/operacoes'
import type { Lancamento } from '../api/tipos'
import { ListaDeExtrato } from './ListaDeExtrato'

function lancamento(over: Partial<Lancamento> = {}): Lancamento {
  return {
    id: 1,
    tipo: 'deposito',
    valor: '200.00',
    saldo_apos: '1200.00',
    contraparte: null,
    data_hora: '2026-09-02T12:00:00Z',
    estorno_de: null,
    estornado_por: null,
    ...over,
  }
}

function comExtrato(...itens: Lancamento[]) {
  return vi
    .spyOn(operacoes, 'buscarExtrato')
    .mockResolvedValue({ transacoes: itens, proximo_cursor: null })
}

beforeEach(() => vi.restoreAllMocks())

describe('o que pode ser estornado', () => {
  it.each([
    ['deposito', true],
    ['saque', true],
    ['transferencia_saida', true],
    ['transferencia_entrada', false],
    ['estorno_entrada', false],
    ['estorno_saida', false],
  ] as const)('%s → botão %s', async (tipo, temBotao) => {
    comExtrato(lancamento({ tipo, estorno_de: tipo.startsWith('estorno') ? 9 : null }))
    render(<ListaDeExtrato contaId={1} versao={0} />)

    await screen.findByText(/./)
    const botao = screen.queryByRole('button', { name: 'Estornar' })
    expect(Boolean(botao)).toBe(temBotao)
  })

  it('o que já foi estornado não oferece de novo', async () => {
    comExtrato(lancamento({ estornado_por: 7 }))
    render(<ListaDeExtrato contaId={1} versao={0} />)

    expect(await screen.findByText('estornado')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Estornar' })).not.toBeInTheDocument()
  })
})

describe('estornar', () => {
  it('chama a API e recarrega o extrato', async () => {
    const extrato = comExtrato(lancamento())
    const estorno = vi
      .spyOn(operacoes, 'estornarLancamento')
      .mockResolvedValue({ saldo_atual: '1000.00', transacao_id: 5 })
    const aoEstornar = vi.fn()

    const usuario = userEvent.setup()
    render(<ListaDeExtrato contaId={1} versao={0} aoEstornar={aoEstornar} />)

    await usuario.click(await screen.findByRole('button', { name: 'Estornar' }))

    await waitFor(() => expect(estorno).toHaveBeenCalledWith(1, 1))
    expect(aoEstornar).toHaveBeenCalled()
    // duas buscas: a inicial e a revalidação
    await waitFor(() => expect(extrato.mock.calls.length).toBeGreaterThanOrEqual(2))
  })

  it('não dispara duas vezes com clique repetido', async () => {
    comExtrato(lancamento())
    let liberar: (v: { saldo_atual: string; transacao_id: number }) => void = () => {}
    const emVoo = new Promise<{ saldo_atual: string; transacao_id: number }>((r) => {
      liberar = r
    })
    const estorno = vi
      .spyOn(operacoes, 'estornarLancamento')
      .mockReturnValue(emVoo)

    const usuario = userEvent.setup()
    render(<ListaDeExtrato contaId={1} versao={0} />)

    const botao = await screen.findByRole('button', { name: 'Estornar' })
    await usuario.click(botao)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Estornando…' })).toBeDisabled(),
    )

    liberar({ saldo_atual: '1000.00', transacao_id: 5 })
    await waitFor(() => expect(estorno).toHaveBeenCalledTimes(1))
  })

  it('mostra a mensagem do backend quando recusado', async () => {
    comExtrato(lancamento())
    vi.spyOn(operacoes, 'estornarLancamento').mockRejectedValue(
      new ErroDaApi('JA_ESTORNADO', 'Este lançamento já foi estornado.', 409),
    )

    const usuario = userEvent.setup()
    render(<ListaDeExtrato contaId={1} versao={0} />)

    await usuario.click(await screen.findByRole('button', { name: 'Estornar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('já foi estornado')
  })
})

describe('sinal do lançamento', () => {
  it('estorno recebido conta como entrada', async () => {
    comExtrato(lancamento({ tipo: 'estorno_entrada', estorno_de: 3 }))
    render(<ListaDeExtrato contaId={1} versao={0} />)

    const valor = await screen.findByText(/\+R\$/)
    expect(valor).toBeInTheDocument()
  })

  it('estorno enviado conta como saída', async () => {
    comExtrato(lancamento({ tipo: 'estorno_saida', estorno_de: 3 }))
    render(<ListaDeExtrato contaId={1} versao={0} />)

    const valor = await screen.findByText(/−R\$/)
    expect(valor).toBeInTheDocument()
  })
})
