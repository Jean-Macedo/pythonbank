import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ErroDaApi } from '../api/client'
import * as operacoes from '../api/operacoes'
import type { Conta } from '../api/tipos'
import { FormularioDeTransacao } from './FormularioDeTransacao'

const CONTA: Conta = {
  id: 1, agencia: '0001', numero: '00100001',
  tipo: 'corrente', apelido: 'Dia a dia', saldo: '1000.00',
}

const OUTRA: Conta = {
  id: 2, agencia: '0001', numero: '00100002',
  tipo: 'poupanca', apelido: 'Reserva', saldo: '500.00',
}

function montar(outras: Conta[] = []) {
  const aoConcluir = vi.fn()
  render(
    <FormularioDeTransacao conta={CONTA} outrasContas={outras} aoConcluir={aoConcluir} />,
  )
  return { aoConcluir, usuario: userEvent.setup() }
}

beforeEach(() => vi.restoreAllMocks())

describe('duplo clique não vira duas transações', () => {
  it('o botão fica desabilitado enquanto a requisição está em voo', async () => {
    // num banco, débito duplicado por clique repetido é o pior defeito de
    // interface possível — pior que a operação não acontecer
    let liberar: (v: { saldo_atual: string; transacao_id: number }) => void = () => {}
    const emVoo = new Promise<{ saldo_atual: string; transacao_id: number }>((r) => {
      liberar = r
    })
    const deposito = vi.spyOn(operacoes, 'depositar').mockReturnValue(emVoo)

    const { usuario } = montar()
    await usuario.type(screen.getByLabelText('Valor'), '100,00')

    const botao = screen.getByRole('button', { name: 'Depositar' })
    await usuario.click(botao)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Enviando…' })).toBeDisabled())

    liberar({ saldo_atual: '1100.00', transacao_id: 1 })
    await waitFor(() => expect(deposito).toHaveBeenCalledTimes(1))
  })
})

describe('valor', () => {
  it('não envia nada quando o valor é inválido', async () => {
    const deposito = vi.spyOn(operacoes, 'depositar')
    const { usuario } = montar()

    await usuario.type(screen.getByLabelText('Valor'), '0')
    await usuario.click(screen.getByRole('button', { name: 'Depositar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/maior que zero/i)
    expect(deposito).not.toHaveBeenCalled()
  })

  it('vai para a API como string, no formato que ela espera', async () => {
    const deposito = vi
      .spyOn(operacoes, 'depositar')
      .mockResolvedValue({ saldo_atual: '1250.50', transacao_id: 9 })

    const { usuario } = montar()
    await usuario.type(screen.getByLabelText('Valor'), '1.234,56')
    await usuario.click(screen.getByRole('button', { name: 'Depositar' }))

    await waitFor(() => expect(deposito).toHaveBeenCalledWith(1, '1234.56'))
    // o segundo argumento é string: dinheiro nunca vira número no cliente
    expect(typeof deposito.mock.calls[0][1]).toBe('string')
  })
})

describe('erro da API', () => {
  it('aparece no formulário, com a mensagem que veio do backend', async () => {
    vi.spyOn(operacoes, 'sacar').mockRejectedValue(
      new ErroDaApi('SALDO_INSUFICIENTE', 'Saldo insuficiente para esta operação.', 422),
    )

    const { usuario, aoConcluir } = montar()
    await usuario.click(screen.getByRole('tab', { name: 'Sacar' }))
    await usuario.type(screen.getByLabelText('Valor'), '99999')
    await usuario.click(screen.getByRole('button', { name: 'Sacar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Saldo insuficiente')
    // e a tela não pode dizer que deu certo
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(aoConcluir).not.toHaveBeenCalled()
  })

  it('o botão volta a funcionar depois da falha', async () => {
    vi.spyOn(operacoes, 'depositar').mockRejectedValue(
      new ErroDaApi('VALOR_INVALIDO', 'Valor inválido.', 422),
    )

    const { usuario } = montar()
    await usuario.type(screen.getByLabelText('Valor'), '10')
    await usuario.click(screen.getByRole('button', { name: 'Depositar' }))

    await screen.findByRole('alert')
    expect(screen.getByRole('button', { name: 'Depositar' })).toBeEnabled()
  })
})

describe('sucesso', () => {
  it('mostra o saldo vindo da resposta, não calculado aqui', async () => {
    vi.spyOn(operacoes, 'depositar').mockResolvedValue({
      saldo_atual: '1100.00',
      transacao_id: 7,
    })

    const { usuario, aoConcluir } = montar()
    await usuario.type(screen.getByLabelText('Valor'), '100')
    await usuario.click(screen.getByRole('button', { name: 'Depositar' }))

    const aviso = await screen.findByRole('status')
    expect(aviso.textContent?.replace(/ /g, ' ')).toContain('R$ 1.100,00')
    expect(aoConcluir).toHaveBeenCalledTimes(1)
  })

  it('limpa o campo para não reenviar por engano', async () => {
    vi.spyOn(operacoes, 'depositar').mockResolvedValue({
      saldo_atual: '1100.00', transacao_id: 7,
    })

    const { usuario } = montar()
    const campo = screen.getByLabelText('Valor')
    await usuario.type(campo, '100')
    await usuario.click(screen.getByRole('button', { name: 'Depositar' }))

    await screen.findByRole('status')
    expect(campo).toHaveValue('')
  })
})

describe('transferência', () => {
  it('usa agência e número da conta escolhida', async () => {
    const transferencia = vi
      .spyOn(operacoes, 'transferir')
      .mockResolvedValue({ saldo_atual: '700.00', transacao_id: 11 })

    const { usuario } = montar([OUTRA])
    await usuario.click(screen.getByRole('tab', { name: 'Transferir' }))
    await usuario.selectOptions(screen.getByLabelText(/conta sua/i), '2')
    await usuario.type(screen.getByLabelText('Valor'), '300')
    await usuario.click(screen.getByRole('button', { name: 'Transferir' }))

    await waitFor(() =>
      expect(transferencia).toHaveBeenCalledWith(1, '300', '0001', '00100002'),
    )
  })

  it('aceita destino digitado quando não é conta própria', async () => {
    const transferencia = vi
      .spyOn(operacoes, 'transferir')
      .mockResolvedValue({ saldo_atual: '900.00', transacao_id: 12 })

    const { usuario } = montar()
    await usuario.click(screen.getByRole('tab', { name: 'Transferir' }))
    await usuario.type(screen.getByLabelText('Agência'), '0001')
    await usuario.type(screen.getByLabelText('Conta'), '00100099')
    await usuario.type(screen.getByLabelText('Valor'), '100')
    await usuario.click(screen.getByRole('button', { name: 'Transferir' }))

    await waitFor(() =>
      expect(transferencia).toHaveBeenCalledWith(1, '100', '0001', '00100099'),
    )
  })
})
