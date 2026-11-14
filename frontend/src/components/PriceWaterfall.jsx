import { money, signed } from '../format.js'

const lakhs = (v) => v.toFixed(1) + ' L'

// "Why this price?" as a waterfall: the model (explained with SHAP) starts
// from the average flat and each detail moves the price up or down.
export default function PriceWaterfall({ result }) {
  const steps = []
  let running = result.base_price
  for (const factor of result.factors) {
    steps.push({ name: factor.name, from: running, to: running + factor.effect, effect: factor.effect })
    running += factor.effect
  }

  const all = [result.base_price, result.predicted_price, ...steps.flatMap((s) => [s.from, s.to])]
  const min = Math.min(...all) * 0.92
  const max = Math.max(...all) * 1.04
  const pos = (v) => ((v - min) / (max - min)) * 100
  const bar = (from, to) => ({ left: pos(Math.min(from, to)) + '%', width: Math.max(pos(Math.max(from, to)) - pos(Math.min(from, to)), 0.6) + '%' })

  return (
    <div className="waterfall-box">
      <p className="hint">Green adds to the price. Red lowers it.</p>
      <ol className="waterfall">
        <li className="waterfall-row waterfall-total">
          <span className="waterfall-name">Average flat</span>
          <span className="waterfall-track"><span className="waterfall-bar" style={bar(min, result.base_price)} /></span>
          <span className="waterfall-value">{lakhs(result.base_price)}</span>
        </li>
        {steps.map((s) => (
          <li key={s.name} className={'waterfall-row ' + (s.effect >= 0 ? 'is-up' : 'is-down')}>
            <span className="waterfall-name">{s.name}</span>
            <span className="waterfall-track"><span className="waterfall-bar" style={bar(s.from, s.to)} /></span>
            <span className="waterfall-value">{signed(s.effect)} L</span>
          </li>
        ))}
        <li className="waterfall-row waterfall-total">
          <span className="waterfall-name">Price in 2017–19</span>
          <span className="waterfall-track"><span className="waterfall-bar" style={bar(min, result.predicted_price)} /></span>
          <span className="waterfall-value">{lakhs(result.predicted_price)}</span>
        </li>
      </ol>
      {result.market_basis !== 'none' && (
        <p className="waterfall-today">
          Prices here went up {result.market_factor.toFixed(1)} times since then
          <strong>= {money(result.today_price, 2)} today</strong>
        </p>
      )}
    </div>
  )
}
