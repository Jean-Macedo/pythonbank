import { useState } from 'react'

import { aplicarTema, temaGuardado, type Tema } from '../tema'

const OPCOES: { valor: Tema; rotulo: string; titulo: string }[] = [
  { valor: 'claro', rotulo: '☀', titulo: 'Tema claro' },
  { valor: 'escuro', rotulo: '☾', titulo: 'Tema escuro' },
  { valor: 'sistema', rotulo: '◐', titulo: 'Seguir o sistema' },
]

export function SeletorDeTema() {
  const [tema, setTema] = useState<Tema>(() => temaGuardado())

  function escolher(novo: Tema) {
    aplicarTema(novo)
    setTema(novo)
  }

  return (
    <div className="abas" role="group" aria-label="Tema da interface"
      style={{ margin: 0, gap: 'var(--e1)' }}>
      {OPCOES.map((opcao) => (
        <button
          key={opcao.valor}
          type="button"
          title={opcao.titulo}
          aria-label={opcao.titulo}
          aria-pressed={tema === opcao.valor}
          className={tema === opcao.valor ? 'botao' : 'botao botao-secundario'}
          style={{ padding: 'var(--e1) var(--e2)' }}
          onClick={() => escolher(opcao.valor)}
        >
          {opcao.rotulo}
        </button>
      ))}
    </div>
  )
}
