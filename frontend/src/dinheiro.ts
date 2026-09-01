/**
 * Formatação monetária.
 *
 * Este módulo **não faz conta**. O saldo exibido é sempre o que a API devolveu;
 * somar ou subtrair aqui reintroduziria em JavaScript o erro de ponto flutuante
 * que o backend evita com `Decimal`.
 *
 * A única direção permitida é `Dinheiro` (string) → texto para a tela.
 */

import type { Dinheiro } from './api/tipos'

const FORMATADOR = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

/** `"1234.50"` → `"R$ 1.234,50"`. */
export function formatar(valor: Dinheiro): string {
  const numero = Number(valor)
  if (!Number.isFinite(numero)) return 'R$ —'
  return FORMATADOR.format(numero)
}

/**
 * Normaliza o que a pessoa digitou para o formato que a API espera.
 *
 * Aceita `1.234,56` e `1234.56`. Devolve `null` quando não dá para entender —
 * o formulário decide o que fazer com isso, e nada é enviado.
 */
export function paraValorDaApi(entrada: string): Dinheiro | null {
  const limpo = entrada.trim().replace(/\s/g, '')
  if (!limpo) return null

  // formato brasileiro: ponto separa milhar, vírgula separa decimal
  const normalizado = limpo.includes(',')
    ? limpo.replace(/\./g, '').replace(',', '.')
    : limpo

  if (!/^\d+(\.\d{1,2})?$/.test(normalizado)) return null
  if (Number(normalizado) <= 0) return null
  return normalizado
}

/** Rótulo e direção de um lançamento, para a lista do extrato. */
export const ENTRADAS = new Set(['deposito', 'transferencia_entrada'])

export function ehEntrada(tipo: string): boolean {
  return ENTRADAS.has(tipo)
}
