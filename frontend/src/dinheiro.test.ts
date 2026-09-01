import { describe, expect, it } from 'vitest'

import { ehEntrada, formatar, paraValorDaApi } from './dinheiro'

describe('formatar', () => {
  it.each([
    ['0.00', 'R$ 0,00'],
    ['1234.50', 'R$ 1.234,50'],
    ['1000000.00', 'R$ 1.000.000,00'],
    ['0.07', 'R$ 0,07'],
  ])('%s vira %s', (entrada, esperado) => {
    // espaço não-quebrável é o que o Intl usa entre símbolo e número
    expect(formatar(entrada).replace(/\u00a0/g, ' ')).toBe(esperado)
  })

  it('não quebra com valor inesperado', () => {
    expect(formatar('nao-e-numero')).toBe('R$ —')
  })
})

describe('paraValorDaApi', () => {
  it.each([
    ['100', '100'],
    ['100,50', '100.50'],
    ['1.234,56', '1234.56'],
    ['1234.56', '1234.56'],
    [' 42 ', '42'],
  ])('%s normaliza para %s', (entrada, esperado) => {
    expect(paraValorDaApi(entrada)).toBe(esperado)
  })

  it.each(['', '0', '0,00', '-5', 'abc', '1,234', '1.2.3'])(
    'recusa %s',
    (entrada) => {
      expect(paraValorDaApi(entrada)).toBeNull()
    },
  )

  it('preserva o valor como texto, sem passar por número', () => {
    // 0.1 + 0.2 em ponto flutuante daria 0.30000000000000004; aqui o valor
    // atravessa como string e chega intacto à API (DT-01)
    expect(paraValorDaApi('0,10')).toBe('0.10')
    expect(paraValorDaApi('999999999999.99')).toBe('999999999999.99')
  })
})

describe('ehEntrada', () => {
  it.each([
    ['deposito', true],
    ['transferencia_entrada', true],
    ['saque', false],
    ['transferencia_saida', false],
  ])('%s -> %s', (tipo, esperado) => {
    expect(ehEntrada(tipo)).toBe(esperado)
  })
})
