import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ErroDaApi } from '../api/client'
import * as operacoes from '../api/operacoes'
import type { Conta } from '../api/tipos'
import { GerenciarConta } from './GerenciarConta'

const CONTA: Conta = {
  id: 1, agencia: '0001', numero: '00100001',
  tipo: 'corrente', apelido: 'Dia a dia', saldo: '0.00',
}

async function abrirPainel(conta: Conta = CONTA) {
  const aoMudar = vi.fn()
  const usuario = userEvent.setup()
  render(<GerenciarConta conta={conta} aoMudar={aoMudar} />)
  await usuario.click(screen.getByRole('button', { name: 'Abrir' }))
  return { aoMudar, usuario }
}

beforeEach(() => vi.restoreAllMocks())

describe('renomear', () => {
  it('envia o apelido novo', async () => {
    const renomear = vi.spyOn(operacoes, 'renomearConta').mockResolvedValue(CONTA)
    const { usuario, aoMudar } = await abrirPainel()

    const campo = screen.getByLabelText('Apelido')
    await usuario.clear(campo)
    await usuario.type(campo, 'Reserva')
    await usuario.click(screen.getByRole('button', { name: 'Salvar apelido' }))

    await waitFor(() => expect(renomear).toHaveBeenCalledWith(1, 'Reserva'))
    expect(aoMudar).toHaveBeenCalled()
  })

  it('apelido em branco vira ausente, não string vazia', async () => {
    const renomear = vi.spyOn(operacoes, 'renomearConta').mockResolvedValue(CONTA)
    const { usuario } = await abrirPainel()

    await usuario.clear(screen.getByLabelText('Apelido'))
    await usuario.click(screen.getByRole('button', { name: 'Salvar apelido' }))

    await waitFor(() => expect(renomear).toHaveBeenCalledWith(1, null))
  })

  it('mostra o erro da API', async () => {
    vi.spyOn(operacoes, 'renomearConta').mockRejectedValue(
      new ErroDaApi('APELIDO_DUPLICADO', 'Você já tem uma conta com este apelido.', 409),
    )
    const { usuario } = await abrirPainel()

    await usuario.click(screen.getByRole('button', { name: 'Salvar apelido' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('já tem uma conta')
  })
})

describe('encerrar', () => {
  it('pede confirmação antes de encerrar', async () => {
    const encerrar = vi.spyOn(operacoes, 'encerrarConta').mockResolvedValue(undefined)
    const { usuario } = await abrirPainel()

    await usuario.click(screen.getByRole('button', { name: 'Encerrar conta' }))
    expect(encerrar).not.toHaveBeenCalled()
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Sim, encerrar' }))
    await waitFor(() => expect(encerrar).toHaveBeenCalledWith(1))
  })

  it('cancelar não encerra', async () => {
    const encerrar = vi.spyOn(operacoes, 'encerrarConta')
    const { usuario } = await abrirPainel()

    await usuario.click(screen.getByRole('button', { name: 'Encerrar conta' }))
    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(encerrar).not.toHaveBeenCalled()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('conta com saldo mostra o erro do backend', async () => {
    vi.spyOn(operacoes, 'encerrarConta').mockRejectedValue(
      new ErroDaApi('CONTA_NAO_ENCERRAVEL', 'Só é possível encerrar com saldo zero.', 422),
    )
    const comSaldo = { ...CONTA, saldo: '1000.00' }
    const { usuario } = await abrirPainel(comSaldo)

    await usuario.click(screen.getByRole('button', { name: 'Encerrar conta' }))
    await usuario.click(screen.getByRole('button', { name: 'Sim, encerrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('saldo zero')
  })

  it('a confirmação mostra o saldo, para a decisão ser informada', async () => {
    const comSaldo = { ...CONTA, saldo: '1234.56' }
    const { usuario } = await abrirPainel(comSaldo)

    await usuario.click(screen.getByRole('button', { name: 'Encerrar conta' }))
    const dialogo = screen.getByRole('alertdialog')
    expect(dialogo.textContent?.replace(/ /g, ' ')).toContain('R$ 1.234,56')
  })
})

describe('trocar de conta', () => {
  it('o campo passa a mostrar o apelido da conta nova', async () => {
    const aoMudar = vi.fn()
    const usuario = userEvent.setup()
    const { rerender } = render(<GerenciarConta conta={CONTA} aoMudar={aoMudar} />)
    await usuario.click(screen.getByRole('button', { name: 'Abrir' }))

    expect(screen.getByLabelText('Apelido')).toHaveValue('Dia a dia')

    rerender(
      <GerenciarConta
        conta={{ ...CONTA, id: 2, apelido: 'Reserva' }}
        aoMudar={aoMudar}
      />,
    )
    expect(screen.getByLabelText('Apelido')).toHaveValue('Reserva')
  })
})
