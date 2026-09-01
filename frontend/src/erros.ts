/**
 * Erro de validação feita no próprio formulário, antes de chamar a API.
 *
 * Existe como tipo próprio para que `Erro` saiba quais mensagens pode exibir.
 * Mostrar a mensagem de qualquer `Error` vazaria texto de defeito interno —
 * um `TypeError` de bug apareceria na tela do usuário — e mostrar só
 * `ErroDaApi` engoliria exatamente as mensagens mais úteis, que são as locais.
 *
 * A validação daqui é para dar resposta rápida. Quem decide de verdade é o
 * backend, que revalida tudo.
 */
export class ErroDeValidacao extends Error {
  constructor(mensagem: string) {
    super(mensagem)
    this.name = 'ErroDeValidacao'
  }
}
