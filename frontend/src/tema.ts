/**
 * Tema da interface.
 *
 * Três estados, não dois: `claro`, `escuro` e `sistema`. O terceiro é o padrão
 * e o mais importante — quem configurou o sistema em escuro não deveria
 * precisar configurar cada site de novo.
 *
 * A escolha vive no `localStorage` e é aplicada como `data-tema` na raiz do
 * documento, que é o que o CSS observa.
 */

export type Tema = 'claro' | 'escuro' | 'sistema'

const CHAVE = 'banco-jean.tema'

export function temaGuardado(): Tema {
  try {
    const valor = localStorage.getItem(CHAVE)
    if (valor === 'claro' || valor === 'escuro') return valor
  } catch {
    // localStorage indisponível: seguir o sistema é sempre seguro
  }
  return 'sistema'
}

export function aplicarTema(tema: Tema): void {
  const raiz = document.documentElement
  if (tema === 'sistema') raiz.removeAttribute('data-tema')
  else raiz.setAttribute('data-tema', tema)

  try {
    if (tema === 'sistema') localStorage.removeItem(CHAVE)
    else localStorage.setItem(CHAVE, tema)
  } catch {
    // sem persistência, a escolha vale só para esta visita
  }
}
