/**
 * O único lugar do frontend que fala HTTP.
 *
 * Existe uma vez só de propósito. Espalhado, cada chamada precisaria lembrar de
 * injetar o token, checar `response.ok` e renovar a sessão — e uma delas
 * acabaria esquecida.
 *
 * O erro que este módulo existe para impedir: `fetch` **não** rejeita a promise
 * em resposta 4xx. Um `HTTPException(422)` do FastAPI é, para o `fetch`, uma
 * resposta bem-sucedida. Sem checar `response.ok`, o saque recusado por saldo
 * insuficiente seguiria pelo caminho de sucesso — e a pessoa acharia que sacou.
 */

import type { CorpoDeErro, Sessao } from './tipos'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ErroDaApi extends Error {
  // campos declarados explicitamente: o template do Vite liga
  // `erasableSyntaxOnly`, que proíbe propriedades no construtor
  readonly codigo: string
  readonly mensagem: string
  readonly status: number

  constructor(
    codigo: string,
    mensagem: string,
    status: number,
    opcoes?: ErrorOptions,
  ) {
    super(mensagem, opcoes)
    this.name = 'ErroDaApi'
    this.codigo = codigo
    this.mensagem = mensagem
    this.status = status
  }

  /** Falha de rede, API fora do ar, CORS — nada que o usuário tenha causado. */
  get ehFalhaDeConexao(): boolean {
    return this.codigo === 'SEM_CONEXAO'
  }

  get ehSessaoInvalida(): boolean {
    return this.status === 401
  }

  /**
   * Token válido, titular inexistente.
   *
   * Não há nada que a pessoa possa fazer com essa sessão: toda rota vai recusar
   * do mesmo jeito. Continuar na tela seria um beco sem saída, então vale como
   * fim de sessão — só que com explicação diferente de "expirou".
   */
  get ehCadastroIncompleto(): boolean {
    return this.codigo === 'CADASTRO_INCOMPLETO'
  }
}

// ---------------------------------------------------------------- sessão ---

const CHAVE = 'banco-jean.sessao'

export function guardarSessao(sessao: Sessao | null): void {
  if (sessao) localStorage.setItem(CHAVE, JSON.stringify(sessao))
  else localStorage.removeItem(CHAVE)
  ouvintes.forEach((ouvinte) => ouvinte(sessao))
}

export function sessaoGuardada(): Sessao | null {
  try {
    const bruto = localStorage.getItem(CHAVE)
    return bruto ? (JSON.parse(bruto) as Sessao) : null
  } catch {
    // localStorage indisponível (janela privada) ou conteúdo corrompido:
    // tratar como "sem sessão" é sempre seguro
    return null
  }
}

type Ouvinte = (sessao: Sessao | null) => void
const ouvintes = new Set<Ouvinte>()

/** Avisa a aplicação quando a sessão cai, para que ela volte ao login. */
export function aoMudarSessao(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte)
  return () => ouvintes.delete(ouvinte)
}

// ------------------------------------------------------------ requisição ---

interface Opcoes {
  metodo?: string
  corpo?: unknown
  autenticada?: boolean
  /** Interno: evita laço infinito quando a própria renovação devolve 401. */
  jaRenovou?: boolean
}

async function corpoDeErro(resposta: Response): Promise<CorpoDeErro> {
  try {
    const dados = (await resposta.json()) as Partial<CorpoDeErro>
    if (dados.codigo && dados.mensagem) return dados as CorpoDeErro
    return {
      codigo: 'ERRO_INESPERADO',
      mensagem: 'Não foi possível completar a operação.',
    }
  } catch {
    return {
      codigo: 'ERRO_INESPERADO',
      mensagem: 'Não foi possível completar a operação.',
    }
  }
}

export async function requisitar<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const { metodo = 'GET', corpo, autenticada = true, jaRenovou = false } = opcoes

  const cabecalhos: Record<string, string> = {}
  if (corpo !== undefined) cabecalhos['Content-Type'] = 'application/json'

  const sessao = sessaoGuardada()
  if (autenticada && sessao) {
    cabecalhos.Authorization = `Bearer ${sessao.access_token}`
  }

  let resposta: Response
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      method: metodo,
      headers: cabecalhos,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    })
  } catch (causa) {
    // só aqui o `fetch` rejeita: falha de rede. Erro HTTP vem como resposta.
    throw new ErroDaApi(
      'SEM_CONEXAO',
      'Não foi possível falar com o servidor. Verifique sua conexão.',
      0,
      { cause: causa },
    )
  }

  // 401 numa rota autenticada: tenta renovar uma vez antes de desistir
  if (resposta.status === 401 && autenticada && !jaRenovou && sessao?.refresh_token) {
    const renovada = await tentarRenovar(sessao.refresh_token)
    if (renovada) {
      guardarSessao(renovada)
      return requisitar<T>(caminho, { ...opcoes, jaRenovou: true })
    }
    guardarSessao(null)
  }

  if (!resposta.ok) {
    const erro = await corpoDeErro(resposta)
    throw new ErroDaApi(erro.codigo, erro.mensagem, resposta.status)
  }

  if (resposta.status === 204) return undefined as T
  return (await resposta.json()) as T
}

async function tentarRenovar(refreshToken: string): Promise<Sessao | null> {
  try {
    const resposta = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!resposta.ok) return null
    return (await resposta.json()) as Sessao
  } catch {
    return null
  }
}
