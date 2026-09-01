import { describe, expect, it } from 'vitest'

import { mascararCpf, mascararData, mascararTelefone, semMascara } from './mascaras'

describe('mascararCpf', () => {
  it.each([
    ['5', '5'],
    ['529', '529'],
    ['5299', '529.9'],
    ['529982', '529.982'],
    ['5299822', '529.982.2'],
    ['529982247', '529.982.247'],
    ['52998224725', '529.982.247-25'],
  ])('%s vira %s', (entrada, esperado) => {
    expect(mascararCpf(entrada)).toBe(esperado)
  })

  it('ignora o que exceder onze dígitos', () => {
    expect(mascararCpf('529982247259999')).toBe('529.982.247-25')
  })

  it('reformata quando já vem formatado', () => {
    expect(mascararCpf('529.982.247-25')).toBe('529.982.247-25')
  })

  it('apagar remove o separador junto', () => {
    // digitou 4, apagou 1: volta a três dígitos sem ponto órfão
    expect(mascararCpf('529.9'.slice(0, 4))).toBe('529')
  })
})

describe('mascararData', () => {
  it.each([
    ['1', '1'],
    ['10', '10'],
    ['100', '10/0'],
    ['1003', '10/03'],
    ['100319', '10/03/19'],
    ['10031995', '10/03/1995'],
  ])('%s vira %s', (entrada, esperado) => {
    expect(mascararData(entrada)).toBe(esperado)
  })

  it('não passa de oito dígitos', () => {
    expect(mascararData('100319951234')).toBe('10/03/1995')
  })
})

describe('mascararTelefone', () => {
  it.each([
    ['11', '11'],
    ['1198', '(11) 98'],
    ['1187654321', '(11) 8765-4321'],
    ['11987654321', '(11) 98765-4321'],
  ])('%s vira %s', (entrada, esperado) => {
    expect(mascararTelefone(entrada)).toBe(esperado)
  })
})

describe('semMascara', () => {
  it('devolve só os dígitos, que é o que a API quer', () => {
    expect(semMascara('529.982.247-25')).toBe('52998224725')
    expect(semMascara('(11) 98765-4321')).toBe('11987654321')
    expect(semMascara('10/03/1995')).toBe('10031995')
  })
})
