/**
 * Máscaras de digitação.
 *
 * Formatam enquanto a pessoa digita, para que ela não precise lembrar onde vão
 * pontos e barras. O backend normaliza tudo de qualquer jeito — a máscara é
 * conforto, não validação.
 *
 * Todas seguem a mesma regra: extraem os dígitos, cortam no comprimento máximo
 * e reinserem os separadores. Isso faz apagar funcionar de forma previsível.
 */

const digitos = (texto: string) => texto.replace(/\D/g, '')

/** `52998224725` → `529.982.247-25` */
export function mascararCpf(entrada: string): string {
  const d = digitos(entrada).slice(0, 11)
  if (d.length <= 3) return d
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
}

/** `10031995` → `10/03/1995` */
export function mascararData(entrada: string): string {
  const d = digitos(entrada).slice(0, 8)
  if (d.length <= 2) return d
  if (d.length <= 4) return `${d.slice(0, 2)}/${d.slice(2)}`
  return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`
}

/** `11987654321` → `(11) 98765-4321` */
export function mascararTelefone(entrada: string): string {
  const d = digitos(entrada).slice(0, 11)
  if (d.length <= 2) return d
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`
  const corte = d.length <= 10 ? 6 : 7 // fixo tem 8 dígitos, celular tem 9
  return `(${d.slice(0, 2)}) ${d.slice(2, corte)}-${d.slice(corte)}`
}

/** O que de fato vai para a API: só os dígitos. */
export const semMascara = digitos
