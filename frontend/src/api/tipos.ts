/**
 * O contrato da API, em tipos.
 *
 * Dinheiro é `string` em todos eles — e isso não é descuido. `JSON.parse`
 * converte número em float de 64 bits, o que desfaria na borda o cuidado que o
 * backend tem com `Decimal`. Tipar como string faz o compilador recusar
 * `conta.saldo + 100` antes de o código existir.
 */

/** Valor monetário. Nunca use em aritmética — veja `dinheiro.ts`. */
export type Dinheiro = string

export type TipoConta = 'corrente' | 'poupanca'

export type TipoTransacao =
  | 'deposito'
  | 'saque'
  | 'transferencia_saida'
  | 'transferencia_entrada'

export interface Cliente {
  id: number
  nome: string
  cpf: string
  email: string
  telefone: string
  data_nascimento: string
}

export interface Conta {
  id: number
  agencia: string
  numero: string
  tipo: TipoConta
  apelido: string | null
  saldo: Dinheiro
}

export interface Lancamento {
  id: number
  tipo: TipoTransacao
  valor: Dinheiro
  saldo_apos: Dinheiro
  contraparte: string | null
  data_hora: string
}

export interface Extrato {
  transacoes: Lancamento[]
  proximo_cursor: string | null
}

export interface ResultadoTransacao {
  saldo_atual: Dinheiro
  transacao_id: number
}

export interface Sessao {
  access_token: string
  refresh_token: string
  expira_em: number
  tipo: string
}

export interface Registro {
  cliente_id: number
  conta_id: number
  sessao: Sessao | null
}

/** Formato único de erro da API. O `codigo` é o que decide o quê fazer. */
export interface CorpoDeErro {
  codigo: string
  mensagem: string
}
