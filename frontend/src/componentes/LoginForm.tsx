import { useState } from 'react'

import { guardarSessao } from '../api/client'
import { entrar, registrar } from '../api/operacoes'
import { ErroDeValidacao } from '../erros'
import { mascararCpf, mascararData, mascararTelefone, semMascara } from '../mascaras'
import { Erro } from './Erro'

type Aba = 'entrar' | 'criar'

/** Entrada e cadastro. O token guardado é o que libera o resto da aplicação. */
interface Props {
  aoEntrar: () => void
  /** Por que a sessão anterior terminou, quando não foi a pessoa que saiu. */
  motivo?: string | null
}

export function LoginForm({ aoEntrar, motivo }: Props) {
  const [aba, setAba] = useState<Aba>('entrar')
  const [erro, setErro] = useState<unknown>(null)
  const [enviando, setEnviando] = useState(false)

  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [nome, setNome] = useState('')
  const [cpf, setCpf] = useState('')
  const [telefone, setTelefone] = useState('')
  const [nascimento, setNascimento] = useState('')

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault()
    if (enviando) return // duplo clique não vira duas requisições
    setEnviando(true)
    setErro(null)
    try {
      if (aba === 'entrar') {
        guardarSessao(await entrar(email, senha))
      } else {
        const criado = await registrar({
          nome,
          // a máscara é para a tela; a API recebe o que ela espera
          cpf: semMascara(cpf),
          email,
          telefone: semMascara(telefone),
          data_nascimento: nascimento,
          senha,
        })
        if (!criado.sessao) {
          setErro(
            new ErroDeValidacao('Cadastro criado. Confirme o e-mail para entrar.'),
          )
          return
        }
        guardarSessao(criado.sessao)
      }
      aoEntrar()
    } catch (causa) {
      setErro(causa)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="cartao" style={{ maxWidth: 420, margin: '10vh auto' }}>
      <h1 style={{ marginTop: 0 }}>Banco Jean</h1>

      {motivo && (
        <p className="erro" role="status">
          {motivo}
        </p>
      )}

      <div className="abas" role="tablist">
        <button
          type="button" role="tab" aria-selected={aba === 'entrar'}
          className={aba === 'entrar' ? 'botao' : 'botao botao-secundario'}
          onClick={() => { setAba('entrar'); setErro(null) }}
        >
          Entrar
        </button>
        <button
          type="button" role="tab" aria-selected={aba === 'criar'}
          className={aba === 'criar' ? 'botao' : 'botao botao-secundario'}
          onClick={() => { setAba('criar'); setErro(null) }}
        >
          Criar conta
        </button>
      </div>

      <form onSubmit={enviar}>
        {aba === 'criar' && (
          <>
            <div className="campo">
              <label htmlFor="nome">Nome completo</label>
              <input id="nome" value={nome} required
                onChange={(e) => setNome(e.target.value)} />
            </div>
            <div className="campo">
              <label htmlFor="cpf">CPF</label>
              <input id="cpf" value={cpf} required placeholder="000.000.000-00"
                inputMode="numeric" autoComplete="off"
                onChange={(e) => setCpf(mascararCpf(e.target.value))} />
            </div>
            <div className="campo">
              <label htmlFor="telefone">Telefone com DDD</label>
              <input id="telefone" value={telefone} required placeholder="(11) 98765-4321"
                inputMode="numeric" autoComplete="off"
                onChange={(e) => setTelefone(mascararTelefone(e.target.value))} />
            </div>
            <div className="campo">
              <label htmlFor="nascimento">Data de nascimento</label>
              <input id="nascimento" value={nascimento} required placeholder="DD/MM/AAAA"
                inputMode="numeric" autoComplete="off"
                onChange={(e) => setNascimento(mascararData(e.target.value))} />
            </div>
          </>
        )}

        <div className="campo">
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" value={email} required
            onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="senha">Senha</label>
          <input id="senha" type="password" value={senha} required
            onChange={(e) => setSenha(e.target.value)} />
        </div>

        <Erro erro={erro} />

        <button className="botao" type="submit" disabled={enviando}>
          {enviando ? 'Aguarde…' : aba === 'entrar' ? 'Entrar' : 'Criar conta'}
        </button>
      </form>
    </div>
  )
}
