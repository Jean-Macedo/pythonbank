import { useState } from 'react'

import { depositar, sacar, transferir } from '../api/operacoes'
import type { Conta } from '../api/tipos'
import { formatar, paraValorDaApi } from '../dinheiro'
import { ErroDeValidacao } from '../erros'
import { Erro } from './Erro'
import { rotuloDaConta } from './SeletorDeConta'

type Operacao = 'deposito' | 'saque' | 'transferencia'

const ROTULOS: Record<Operacao, string> = {
  deposito: 'Depositar',
  saque: 'Sacar',
  transferencia: 'Transferir',
}

interface Props {
  conta: Conta
  outrasContas: Conta[]
  aoConcluir: () => void
}

/**
 * Depósito, saque e transferência na conta ativa.
 *
 * Duas garantias que este componente precisa dar:
 *
 * 1. **Duplo clique não vira duas transações.** O botão é desabilitado enquanto
 *    a requisição está em voo. Num banco, débito duplicado é o pior defeito
 *    possível de interface.
 * 2. **Nada é calculado aqui.** O saldo mostrado depois vem da resposta da API,
 *    nunca de aritmética local (DT-01).
 */
export function FormularioDeTransacao({ conta, outrasContas, aoConcluir }: Props) {
  const [operacao, setOperacao] = useState<Operacao>('deposito')
  const [valor, setValor] = useState('')
  const [destino, setDestino] = useState('')
  const [agenciaLivre, setAgenciaLivre] = useState('')
  const [numeroLivre, setNumeroLivre] = useState('')
  const [erro, setErro] = useState<unknown>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  function trocarOperacao(nova: Operacao) {
    setOperacao(nova)
    setErro(null)
    setAviso(null)
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault()
    if (enviando) return // a guarda contra duplo clique

    setErro(null)
    setAviso(null)

    const normalizado = paraValorDaApi(valor)
    if (normalizado === null) {
      setErro(new ErroDeValidacao('Informe um valor válido, maior que zero.'))
      return
    }

    let agencia = agenciaLivre.trim()
    let numero = numeroLivre.trim()
    if (operacao === 'transferencia' && destino) {
      const escolhida = outrasContas.find((c) => String(c.id) === destino)
      if (escolhida) {
        agencia = escolhida.agencia
        numero = escolhida.numero
      }
    }

    setEnviando(true)
    try {
      const resultado =
        operacao === 'deposito'
          ? await depositar(conta.id, normalizado)
          : operacao === 'saque'
            ? await sacar(conta.id, normalizado)
            : await transferir(conta.id, normalizado, agencia, numero)

      setValor('')
      setAgenciaLivre('')
      setNumeroLivre('')
      // o saldo vem da resposta, não de conta feita aqui
      setAviso(`${ROTULOS[operacao]} concluído. Saldo: ${formatar(resultado.saldo_atual)}`)
      aoConcluir()
    } catch (causa) {
      setErro(causa)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="cartao" style={{ marginBottom: 'var(--e4)' }}>
      <div className="abas" role="tablist" aria-label="Operação">
        {(Object.keys(ROTULOS) as Operacao[]).map((chave) => (
          <button
            key={chave} type="button" role="tab"
            aria-selected={operacao === chave}
            className={operacao === chave ? 'botao' : 'botao botao-secundario'}
            onClick={() => trocarOperacao(chave)}
          >
            {ROTULOS[chave]}
          </button>
        ))}
      </div>

      <form onSubmit={enviar}>
        <div className="campo">
          <label htmlFor="valor">Valor</label>
          <input
            id="valor" inputMode="decimal" value={valor} required
            placeholder="0,00" autoComplete="off"
            onChange={(e) => setValor(e.target.value)}
          />
        </div>

        {operacao === 'transferencia' && (
          <>
            {outrasContas.length > 0 && (
              <div className="campo">
                <label htmlFor="destino">Para uma conta sua</label>
                <select
                  id="destino" value={destino}
                  onChange={(e) => setDestino(e.target.value)}
                >
                  <option value="">Outra pessoa…</option>
                  {outrasContas.map((c) => (
                    <option key={c.id} value={c.id}>{rotuloDaConta(c)}</option>
                  ))}
                </select>
              </div>
            )}

            {!destino && (
              <div className="linha">
                <div className="campo" style={{ flex: 1 }}>
                  <label htmlFor="agencia">Agência</label>
                  <input
                    id="agencia" value={agenciaLivre} required placeholder="0001"
                    onChange={(e) => setAgenciaLivre(e.target.value)}
                  />
                </div>
                <div className="campo" style={{ flex: 2 }}>
                  <label htmlFor="numero">Conta</label>
                  <input
                    id="numero" value={numeroLivre} required placeholder="00100001"
                    onChange={(e) => setNumeroLivre(e.target.value)}
                  />
                </div>
              </div>
            )}
          </>
        )}

        <Erro erro={erro} />
        {aviso && <p className="sucesso" role="status">{aviso}</p>}

        <button className="botao" type="submit" disabled={enviando}>
          {enviando ? 'Enviando…' : ROTULOS[operacao]}
        </button>
      </form>
    </section>
  )
}
