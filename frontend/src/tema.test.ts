import { beforeEach, describe, expect, it } from 'vitest'

import { aplicarTema, temaGuardado } from './tema'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-tema')
})

describe('tema', () => {
  it('o padrão é seguir o sistema', () => {
    expect(temaGuardado()).toBe('sistema')
  })

  it('escolha manual marca a raiz do documento', () => {
    aplicarTema('escuro')
    expect(document.documentElement.getAttribute('data-tema')).toBe('escuro')
    expect(temaGuardado()).toBe('escuro')
  })

  it('voltar para o sistema remove a marca', () => {
    aplicarTema('claro')
    aplicarTema('sistema')
    expect(document.documentElement.hasAttribute('data-tema')).toBe(false)
    expect(temaGuardado()).toBe('sistema')
  })

  it('a escolha sobrevive ao recarregamento', () => {
    aplicarTema('claro')
    expect(temaGuardado()).toBe('claro')
  })

  it('valor corrompido não quebra: cai no sistema', () => {
    localStorage.setItem('banco-jean.tema', 'roxo')
    expect(temaGuardado()).toBe('sistema')
  })
})
