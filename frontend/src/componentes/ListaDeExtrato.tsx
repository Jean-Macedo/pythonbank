import { useCallback, useEffect, useState } from 'react'

import { buscarExtrato } from '../api/operacoes'
import type { Lancamento } from '../api/tipos'
import { ehEntrada, formatar } from '../dinheiro'
import { Erro } from './Erro'

const ROTULO: Record<string, string> = {
  deposito: 'Depósito',
  saque: 'Saque',
  transferencia_saida: 'Transferência enviada',
  transferencia_entrada: 'Transferência recebida',
}

function quando(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

/** Histórico paginado por cursor. Entradas e saídas em cores distintas. */
export function ListaDeExtrato({ contaId, versao }: { contaId: number; versao: number }) {
  const [lancamentos, setLancamentos] = useState<Lancamento[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<unknown>(null)

  const carregar = useCallback(
    async (posicao: string | null, acumular: boolean) => {
      setCarregando(true)
      setErro(null)
      try {
        const pagina = await buscarExtrato(contaId, posicao)
        setLancamentos((atuais) =>
          acumular ? [...atuais, ...pagina.transacoes] : pagina.transacoes,
        )
        setCursor(pagina.proximo_cursor)
      } catch (causa) {
        setErro(causa)
      } finally {
        setCarregando(false)
      }
    },
    [contaId],
  )

  // `versao` muda a cada transação concluída: é o que faz o extrato
  // recarregar sem que este componente precise saber o que aconteceu
  useEffect(() => {
    void carregar(null, false)
  }, [carregar, versao])

  return (
    <section className="cartao">
      <h2 style={{ margin: '0 0 var(--e3)', fontSize: '1rem' }}>Extrato</h2>

      <Erro erro={erro} />

      {lancamentos.length === 0 && !carregando && !erro && (
        <p style={{ color: 'var(--tinta-3)' }}>Nenhuma movimentação ainda.</p>
      )}

      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {lancamentos.map((lancamento) => {
          const entrada = ehEntrada(lancamento.tipo)
          return (
            <li
              key={lancamento.id}
              className="entre"
              style={{
                padding: 'var(--e2) 0',
                borderBottom: '1px solid var(--linha)',
                gap: 'var(--e3)',
              }}
            >
              <span>
                <strong style={{ fontWeight: 500 }}>
                  {ROTULO[lancamento.tipo] ?? lancamento.tipo}
                </strong>
                <br />
                <small style={{ color: 'var(--tinta-3)' }}>
                  {quando(lancamento.data_hora)}
                  {lancamento.contraparte && ` · ${lancamento.contraparte}`}
                </small>
              </span>
              <span
                className="dinheiro"
                style={{ color: entrada ? 'var(--entrada)' : 'var(--saida)' }}
              >
                {entrada ? '+' : '−'}
                {formatar(lancamento.valor)}
              </span>
            </li>
          )
        })}
      </ul>

      {cursor && (
        <button
          type="button" className="botao botao-secundario"
          style={{ marginTop: 'var(--e3)' }}
          disabled={carregando}
          onClick={() => void carregar(cursor, true)}
        >
          {carregando ? 'Carregando…' : 'Carregar mais'}
        </button>
      )}
    </section>
  )
}
