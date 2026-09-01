import { useCallback, useEffect, useState } from 'react'

import { ErroDaApi, aoMudarSessao, guardarSessao, sessaoGuardada } from './api/client'
import { listarContas, meusDados } from './api/operacoes'
import type { Cliente, Conta } from './api/tipos'
import { Cabecalho } from './componentes/Cabecalho'
import { Erro } from './componentes/Erro'
import { FormularioDeTransacao } from './componentes/FormularioDeTransacao'
import { GerenciarConta } from './componentes/GerenciarConta'
import { ListaDeExtrato } from './componentes/ListaDeExtrato'
import { LoginForm } from './componentes/LoginForm'
import { PainelDeSaldo } from './componentes/PainelDeSaldo'
import { SeletorDeConta } from './componentes/SeletorDeConta'

export function App() {
  const [autenticado, setAutenticado] = useState(() => sessaoGuardada() !== null)
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [contas, setContas] = useState<Conta[]>([])
  const [contaAtivaId, setContaAtivaId] = useState<number | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<unknown>(null)
  const [motivoDaSaida, setMotivoDaSaida] = useState<string | null>(null)
  // incrementado a cada transação: faz saldo e extrato buscarem de novo
  const [versao, setVersao] = useState(0)

  // a sessão pode cair de dentro do cliente HTTP, quando a renovação falha
  useEffect(() => aoMudarSessao((sessao) => setAutenticado(sessao !== null)), [])

  const recarregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [dados, lista] = await Promise.all([meusDados(), listarContas()])
      setCliente(dados)
      setContas(lista)
      setContaAtivaId((atual) =>
        atual !== null && lista.some((c) => c.id === atual)
          ? atual
          : (lista[0]?.id ?? null),
      )
    } catch (causa) {
      if (causa instanceof ErroDaApi && causa.ehCadastroIncompleto) {
        // não há rota que funcione com essa sessão; ficar na tela seria um
        // beco sem saída
        setMotivoDaSaida(causa.mensagem)
        guardarSessao(null)
        return
      }
      // 401 já derruba a sessão pelo cliente HTTP; mostrar erro aqui seria ruído
      if (!(causa instanceof ErroDaApi && causa.ehSessaoInvalida)) setErro(causa)
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => {
    if (autenticado) void recarregar()
    else { setCliente(null); setContas([]); setContaAtivaId(null) }
  }, [autenticado, recarregar])

  function aoConcluirTransacao() {
    setVersao((v) => v + 1)
    void recarregar() // o saldo exibido vem sempre da API
  }

  if (!autenticado) {
    return (
      <LoginForm
        motivo={motivoDaSaida}
        aoEntrar={() => {
          setMotivoDaSaida(null)
          setAutenticado(true)
        }}
      />
    )
  }

  const ativa = contas.find((c) => c.id === contaAtivaId) ?? null

  return (
    <div className="app">
      <Cabecalho cliente={cliente} />

      <Erro erro={erro} />

      {carregando && contas.length === 0 && (
        <p style={{ color: 'var(--tinta-3)' }}>Carregando suas contas…</p>
      )}

      {contas.length > 0 && (
        <SeletorDeConta
          contas={contas}
          ativa={ativa}
          aoSelecionar={(conta) => setContaAtivaId(conta.id)}
          aoAbrir={() => void recarregar()}
        />
      )}

      {ativa && (
        <>
          <PainelDeSaldo conta={ativa} />
          <FormularioDeTransacao
            conta={ativa}
            outrasContas={contas.filter((c) => c.id !== ativa.id)}
            aoConcluir={aoConcluirTransacao}
          />
          <ListaDeExtrato contaId={ativa.id} versao={versao} />
          <GerenciarConta conta={ativa} aoMudar={() => void recarregar()} />
        </>
      )}

      {!carregando && contas.length === 0 && !erro && (
        <div className="cartao">
          <p>Você ainda não tem contas abertas.</p>
          <button className="botao" type="button" onClick={() => guardarSessao(null)}>
            Sair
          </button>
        </div>
      )}
    </div>
  )
}
