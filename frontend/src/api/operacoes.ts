/**
 * As operações da API, uma função por rota.
 *
 * Os componentes chamam daqui e nunca montam URL nem tocam em `fetch`.
 */

import { requisitar } from './client'
import type {
  Cliente, Conta, Dinheiro, Extrato, Registro,
  ResultadoTransacao, Sessao, TipoConta,
} from './tipos'

// ----------------------------------------------------------- autenticação --

export interface DadosDeRegistro {
  nome: string
  cpf: string
  email: string
  telefone: string
  data_nascimento: string
  senha: string
}

export const registrar = (dados: DadosDeRegistro) =>
  requisitar<Registro>('/auth/registro', {
    metodo: 'POST', corpo: dados, autenticada: false,
  })

export const entrar = (email: string, senha: string) =>
  requisitar<Sessao>('/auth/login', {
    metodo: 'POST', corpo: { email, senha }, autenticada: false,
  })

// ---------------------------------------------------------------- titular --

export const meusDados = () => requisitar<Cliente>('/api/me')

// ----------------------------------------------------------------- contas --

export const listarContas = () =>
  requisitar<{ contas: Conta[] }>('/api/contas').then((r) => r.contas)

export const abrirConta = (tipo: TipoConta, apelido: string | null) =>
  requisitar<Conta>('/api/contas', { metodo: 'POST', corpo: { tipo, apelido } })

export const renomearConta = (contaId: number, apelido: string | null) =>
  requisitar<Conta>(`/api/contas/${contaId}`, { metodo: 'PATCH', corpo: { apelido } })

export const encerrarConta = (contaId: number) =>
  requisitar<void>(`/api/contas/${contaId}`, { metodo: 'DELETE' })

// ----------------------------------------------------------- movimentação --

export const depositar = (contaId: number, valor: Dinheiro) =>
  requisitar<ResultadoTransacao>(`/api/contas/${contaId}/deposito`, {
    metodo: 'POST', corpo: { valor },
  })

export const sacar = (contaId: number, valor: Dinheiro) =>
  requisitar<ResultadoTransacao>(`/api/contas/${contaId}/saque`, {
    metodo: 'POST', corpo: { valor },
  })

export const transferir = (
  contaId: number, valor: Dinheiro, agenciaDestino: string, numeroDestino: string,
) =>
  requisitar<ResultadoTransacao>(`/api/contas/${contaId}/transferencia`, {
    metodo: 'POST',
    corpo: {
      valor,
      agencia_destino: agenciaDestino,
      numero_destino: numeroDestino,
    },
  })

// ---------------------------------------------------------------- extrato --

export const buscarExtrato = (contaId: number, cursor?: string | null) => {
  const parametros = new URLSearchParams({ limite: '20' })
  if (cursor) parametros.set('cursor', cursor)
  return requisitar<Extrato>(`/api/contas/${contaId}/extrato?${parametros}`)
}
