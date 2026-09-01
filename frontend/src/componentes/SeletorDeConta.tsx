import { useState } from 'react'

import { abrirConta } from '../api/operacoes'
import type { Conta, TipoConta } from '../api/tipos'
import { formatar } from '../dinheiro'
import { Erro } from './Erro'

interface Props {
  contas: Conta[]
  ativa: Conta | null
  aoSelecionar: (conta: Conta) => void
  aoAbrir: () => void
}

export function rotuloDaConta(conta: Conta): string {
  const base = conta.apelido ?? (conta.tipo === 'corrente' ? 'Corrente' : 'Poupança')
  return `${base} · ${conta.agencia}/${conta.numero}`
}

/** Lista as contas do titular e permite abrir mais uma. */
export function SeletorDeConta({ contas, ativa, aoSelecionar, aoAbrir }: Props) {
  const [abrindo, setAbrindo] = useState(false)
  const [tipo, setTipo] = useState<TipoConta>('poupanca')
  const [apelido, setApelido] = useState('')
  const [erro, setErro] = useState<unknown>(null)
  const [enviando, setEnviando] = useState(false)

  async function criar(evento: React.FormEvent) {
    evento.preventDefault()
    if (enviando) return
    setEnviando(true)
    setErro(null)
    try {
      await abrirConta(tipo, apelido.trim() || null)
      setApelido('')
      setAbrindo(false)
      aoAbrir()
    } catch (causa) {
      setErro(causa)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="cartao" style={{ marginBottom: 'var(--e4)' }}>
      <div className="entre">
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Suas contas</h2>
        <button
          type="button" className="botao botao-secundario"
          onClick={() => setAbrindo((v) => !v)}
        >
          {abrindo ? 'Cancelar' : 'Abrir conta'}
        </button>
      </div>

      <ul style={{ listStyle: 'none', padding: 0, margin: 'var(--e3) 0 0' }}>
        {contas.map((conta) => (
          <li key={conta.id}>
            <button
              type="button"
              aria-current={ativa?.id === conta.id}
              onClick={() => aoSelecionar(conta)}
              className="entre"
              style={{
                width: '100%', textAlign: 'left', cursor: 'pointer',
                background: ativa?.id === conta.id
                  ? 'color-mix(in srgb, var(--entrada) 10%, transparent)'
                  : 'transparent',
                border: '1px solid var(--linha)',
                borderRadius: 'var(--raio)',
                padding: 'var(--e2) var(--e3)',
                marginBottom: 'var(--e2)',
              }}
            >
              <span>{rotuloDaConta(conta)}</span>
              <span className="dinheiro">{formatar(conta.saldo)}</span>
            </button>
          </li>
        ))}
      </ul>

      {abrindo && (
        <form onSubmit={criar} style={{ marginTop: 'var(--e3)' }}>
          <div className="campo">
            <label htmlFor="tipo-conta">Tipo</label>
            <select id="tipo-conta" value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoConta)}>
              <option value="corrente">Corrente</option>
              <option value="poupanca">Poupança</option>
            </select>
          </div>
          <div className="campo">
            <label htmlFor="apelido">Apelido (opcional)</label>
            <input id="apelido" value={apelido}
              onChange={(e) => setApelido(e.target.value)} />
          </div>
          <Erro erro={erro} />
          <button className="botao" type="submit" disabled={enviando}>
            {enviando ? 'Abrindo…' : 'Abrir'}
          </button>
        </form>
      )}
    </section>
  )
}
