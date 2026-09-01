import { ErroDaApi } from '../api/client'
import { ErroDeValidacao } from '../erros'

/**
 * Mensagem de erro no contexto de quem a causou.
 *
 * Só dois tipos têm mensagem exibível: a que veio da API (já em português, e
 * escolhida para o usuário) e a validação local. Qualquer outra coisa vira texto
 * genérico — a mensagem de um `TypeError` de defeito interno não é assunto de
 * quem está usando o banco.
 *
 * O `codigo` é o que decide comportamento; a mensagem é só para ler.
 */
export function Erro({ erro }: { erro: unknown }) {
  if (!erro) return null

  const mensagem =
    erro instanceof ErroDaApi || erro instanceof ErroDeValidacao
      ? erro.message
      : 'Algo deu errado. Tente novamente.'

  return (
    <p className="erro" role="alert">
      {mensagem}
    </p>
  )
}
