import { useEffect, useState } from 'react'

import { encerrarConta, renomearConta } from '../api/operacoes'
import type { Conta } from '../api/tipos'
import { formatar } from '../dinheiro'
import { Erro } from './Erro'

interface Props {
  conta: Conta
  aoMudar: () => void
}

/**
 * Renomear e encerrar a conta ativa.
 *
 * A API sempre teve `PATCH` e `DELETE`; faltava a interface — a pessoa podia
 * abrir contas e não tinha como corrigir um apelido nem se livrar de uma que
 * não usa mais.
 *
 * O encerramento pede confirmação porque é irreversível: a conta é desativada,
 * não apagada, e não há como reabri-la.
 */
export function GerenciarConta({ conta, aoMudar }: Props) {
  const [aberto, setAberto] = useState(false)
  const [apelido, setApelido] = useState(conta.apelido ?? '')
  const [confirmando, setConfirmando] = useState(false)
  const [erro, setErro] = useState<unknown>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  // trocar de conta enquanto o painel está aberto não pode deixar o campo
  // mostrando o apelido da conta anterior
  useEffect(() => {
    setApelido(conta.apelido ?? '')
    setConfirmando(false)
    setErro(null)
    setAviso(null)
  }, [conta.id, conta.apelido])

  async function renomear(evento: React.FormEvent) {
    evento.preventDefault()
    if (enviando) return
    setEnviando(true)
    setErro(null)
    setAviso(null)
    try {
      await renomearConta(conta.id, apelido.trim() || null)
      setAviso('Apelido atualizado.')
      aoMudar()
    } catch (causa) {
      setErro(causa)
    } finally {
      setEnviando(false)
    }
  }

  async function encerrar() {
    if (enviando) return
    setEnviando(true)
    setErro(null)
    setAviso(null)
    try {
      await encerrarConta(conta.id)
      setConfirmando(false)
      setAberto(false)
      aoMudar()
    } catch (causa) {
      setErro(causa)
      setConfirmando(false)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="cartao" style={{ marginBottom: 'var(--e4)' }}>
      <div className="entre">
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Gerenciar esta conta</h2>
        <button
          type="button"
          className="botao botao-secundario"
          aria-expanded={aberto}
          onClick={() => setAberto((v) => !v)}
        >
          {aberto ? 'Fechar' : 'Abrir'}
        </button>
      </div>

      {aberto && (
        <div style={{ marginTop: 'var(--e3)' }}>
          <form onSubmit={renomear}>
            <div className="campo">
              <label htmlFor="apelido-conta">Apelido</label>
              <input
                id="apelido-conta"
                value={apelido}
                maxLength={60}
                placeholder="Sem apelido"
                onChange={(e) => setApelido(e.target.value)}
              />
            </div>
            <button className="botao" type="submit" disabled={enviando}>
              {enviando ? 'Salvando…' : 'Salvar apelido'}
            </button>
          </form>

          <hr
            style={{
              border: 0,
              borderTop: '1px solid var(--linha)',
              margin: 'var(--e4) 0',
            }}
          />

          {!confirmando ? (
            <>
              <p style={{ color: 'var(--tinta-3)', fontSize: '.9rem', margin: 0 }}>
                Encerrar exige saldo zero. A conta some da lista, mas o histórico
                dela continua existindo.
              </p>
              <button
                type="button"
                className="botao botao-secundario"
                style={{ marginTop: 'var(--e2)', color: 'var(--saida)' }}
                onClick={() => setConfirmando(true)}
              >
                Encerrar conta
              </button>
            </>
          ) : (
            <div role="alertdialog" aria-label="Confirmar encerramento">
              <p style={{ margin: '0 0 var(--e2)' }}>
                Encerrar esta conta? O saldo atual é{' '}
                <strong className="dinheiro">{formatar(conta.saldo)}</strong>. Não
                há como reabrir.
              </p>
              <div className="linha">
                <button
                  type="button"
                  className="botao"
                  style={{ background: 'var(--saida)' }}
                  disabled={enviando}
                  onClick={() => void encerrar()}
                >
                  {enviando ? 'Encerrando…' : 'Sim, encerrar'}
                </button>
                <button
                  type="button"
                  className="botao botao-secundario"
                  onClick={() => setConfirmando(false)}
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          <Erro erro={erro} />
          {aviso && (
            <p className="sucesso" role="status">
              {aviso}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
