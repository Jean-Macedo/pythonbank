import type { Conta } from '../api/tipos'
import { formatar } from '../dinheiro'
import { rotuloDaConta } from './SeletorDeConta'

/**
 * O saldo da conta ativa.
 *
 * O valor exibido é sempre o que a API devolveu. Nunca é calculado aqui —
 * somar em JavaScript reintroduziria o erro de ponto flutuante que o backend
 * evita com `Decimal`.
 */
export function PainelDeSaldo({ conta }: { conta: Conta }) {
  return (
    <section
      className="cartao"
      aria-label="Saldo da conta ativa"
      style={{ marginBottom: 'var(--e4)' }}
    >
      <p style={{ margin: 0, color: 'var(--tinta-3)', fontSize: '.85rem' }}>
        {rotuloDaConta(conta)}
      </p>
      <p
        className="dinheiro"
        style={{ margin: 'var(--e1) 0 0', fontSize: '2rem', fontWeight: 600 }}
      >
        {formatar(conta.saldo)}
      </p>
    </section>
  )
}
