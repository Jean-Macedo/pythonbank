import { guardarSessao } from '../api/client'
import type { Cliente } from '../api/tipos'
import { SeletorDeTema } from './SeletorDeTema'

export function Cabecalho({ cliente }: { cliente: Cliente | null }) {
  return (
    <header
      className="entre"
      style={{
        marginBottom: 'var(--e5)',
        paddingBottom: 'var(--e3)',
        borderBottom: '1px solid var(--linha)',
      }}
    >
      <div>
        <strong>Banco Jean</strong>
        {cliente && (
          <span style={{ color: 'var(--tinta-3)' }}> · {cliente.nome}</span>
        )}
      </div>
      <div className="linha">
        <SeletorDeTema />
        <button
          type="button" className="botao botao-secundario"
          onClick={() => guardarSessao(null)}
        >
          Sair
        </button>
      </div>
    </header>
  )
}
