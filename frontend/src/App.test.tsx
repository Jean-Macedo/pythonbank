import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { ErroDaApi, guardarSessao } from './api/client'
import * as operacoes from './api/operacoes'
import type { Cliente, Conta, Sessao } from './api/tipos'

const SESSAO: Sessao = {
  access_token: 't', refresh_token: 'r', expira_em: 3600, tipo: 'bearer',
}
const CLIENTE: Cliente = {
  id: 1, nome: 'Jean Macedo', cpf: '52998224725',
  email: 'jean@exemplo.com', telefone: '11987654321',
  data_nascimento: '1995-03-10',
}
const CORRENTE: Conta = {
  id: 1, agencia: '0001', numero: '00100001',
  tipo: 'corrente', apelido: 'Dia a dia', saldo: '1000.00',
}
const POUPANCA: Conta = {
  id: 2, agencia: '0001', numero: '00100002',
  tipo: 'poupanca', apelido: 'Reserva', saldo: '500.00',
}

/** O saldo aparece no seletor e no painel; aqui interessa o do painel. */
async function saldoEmDestaque() {
  const painel = await screen.findByRole('region', { name: 'Saldo da conta ativa' })
  return within(painel)
}

function comBackend(contas: Conta[] = [CORRENTE, POUPANCA]) {
  vi.spyOn(operacoes, 'meusDados').mockResolvedValue(CLIENTE)
  const listar = vi.spyOn(operacoes, 'listarContas').mockResolvedValue(contas)
  vi.spyOn(operacoes, 'buscarExtrato').mockResolvedValue({
    transacoes: [], proximo_cursor: null,
  })
  return listar
}

beforeEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('guarda de autenticação', () => {
  it('sem sessão, mostra o login', () => {
    render(<App />)
    expect(screen.getByRole('tab', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('com sessão, carrega as contas', async () => {
    guardarSessao(SESSAO)
    comBackend()
    render(<App />)

    expect(await screen.findByText(/Jean Macedo/)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Dia a dia/ })).toBeInTheDocument()
  })

  it('sair volta para o login', async () => {
    guardarSessao(SESSAO)
    comBackend()
    const usuario = userEvent.setup()
    render(<App />)

    await screen.findByText(/Jean Macedo/)
    await usuario.click(screen.getByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('tab', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('cadastro incompleto volta ao login explicando o motivo', async () => {
    // token válido cujo titular não existe: nenhuma rota vai funcionar, então
    // ficar na tela seria um beco sem saída
    guardarSessao(SESSAO)
    const incompleto = new ErroDaApi(
      'CADASTRO_INCOMPLETO',
      'Seu usuário existe, mas o cadastro do titular não foi concluído.',
      403,
    )
    vi.spyOn(operacoes, 'meusDados').mockRejectedValue(incompleto)
    vi.spyOn(operacoes, 'listarContas').mockRejectedValue(incompleto)
    render(<App />)

    expect(await screen.findByRole('tab', { name: 'Entrar' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(/cadastro do titular/i)
    expect(localStorage.getItem('banco-jean.sessao')).toBeNull()
  })

  it('sessão derrubada por 401 leva de volta ao login sem mostrar erro', async () => {
    // o cliente HTTP já limpa a sessão; a tela não deve piscar mensagem de erro
    guardarSessao(SESSAO)
    vi.spyOn(operacoes, 'meusDados').mockRejectedValue(
      new ErroDaApi('NAO_AUTENTICADO', 'Sessão expirada.', 401),
    )
    vi.spyOn(operacoes, 'listarContas').mockRejectedValue(
      new ErroDaApi('NAO_AUTENTICADO', 'Sessão expirada.', 401),
    )
    render(<App />)

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })
})

describe('conta ativa', () => {
  it('a primeira conta é selecionada sozinha', async () => {
    guardarSessao(SESSAO)
    comBackend()
    render(<App />)

    const painel = await saldoEmDestaque()
    expect(painel.getByText(/R\$\s*1\.000,00/)).toBeInTheDocument()
  })

  it('trocar de conta troca o saldo e recarrega o extrato', async () => {
    guardarSessao(SESSAO)
    comBackend()
    const extrato = vi.spyOn(operacoes, 'buscarExtrato')
    const usuario = userEvent.setup()
    render(<App />)

    await saldoEmDestaque()
    await usuario.click(screen.getByRole('button', { name: /Reserva/ }))

    await waitFor(async () =>
      expect((await saldoEmDestaque()).getByText(/R\$\s*500,00/)).toBeInTheDocument(),
    )
    await waitFor(() => expect(extrato).toHaveBeenCalledWith(2, null))
  })
})

describe('depois de uma transação', () => {
  it('o saldo é buscado de novo, não calculado na tela', async () => {
    guardarSessao(SESSAO)
    const listar = comBackend()
    vi.spyOn(operacoes, 'depositar').mockResolvedValue({
      saldo_atual: '1100.00', transacao_id: 5,
    })
    // a API passa a devolver o saldo novo
    listar.mockResolvedValue([{ ...CORRENTE, saldo: '1100.00' }, POUPANCA])

    const usuario = userEvent.setup()
    render(<App />)

    await screen.findByLabelText('Valor')
    await usuario.type(screen.getByLabelText('Valor'), '100')
    await usuario.click(screen.getByRole('button', { name: 'Depositar' }))

    await waitFor(async () =>
      expect((await saldoEmDestaque()).getByText(/R\$\s*1\.100,00/)).toBeInTheDocument(),
    )
    // duas chamadas: a inicial e a revalidação
    await waitFor(() => expect(listar.mock.calls.length).toBeGreaterThanOrEqual(2))
  })
})

describe('sem contas', () => {
  it('não quebra e oferece sair', async () => {
    guardarSessao(SESSAO)
    comBackend([])
    render(<App />)

    expect(await screen.findByText(/ainda não tem contas/i)).toBeInTheDocument()
  })
})
