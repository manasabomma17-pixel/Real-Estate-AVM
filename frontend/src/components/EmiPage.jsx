import { useState } from 'react'
import { money, rupees } from '../format.js'
import EmiCalculator, { emiFor } from './EmiCalculator.jsx'

// The home loan EMI for a flat's price, with suggestions on which plan
// suits best. It starts from the last price check, and any price can be typed.
export default function EmiPage({ check, go }) {
  const fromCheck = check?.result.today_price
  const [lakhs, setLakhs] = useState(fromCheck ? String(Math.round(fromCheck)) : '')
  const [plan, setPlan] = useState({ down: 25, rate: 8.5, years: 20 })
  const [income, setIncome] = useState('')
  const price = Number(lakhs)

  return (
    <>
      <section className="intro">
        <h1>Loan EMI</h1>
        <p className="lede">How much you pay the bank each month.</p>
      </section>

      <div className="sheet places-form">
        <div className="field-grid field-grid-2">
          <div className="field">
            <label htmlFor="emi-price">Flat price <span className="optional">in Lakhs</span></label>
            <div className="input-unit">
              <input id="emi-price" type="number" inputMode="decimal" min={1} step="any" value={lakhs}
                placeholder="e.g. 157 for ₹1.57 Cr" onChange={(e) => setLakhs(e.target.value)} />
              <span>{price > 0 ? money(price, 2) : 'Lakhs'}</span>
            </div>
          </div>
          <div className="field">
            <label htmlFor="emi-income">Your monthly salary <span className="optional">in hand, optional</span></label>
            <div className="input-unit">
              <input id="emi-income" type="number" inputMode="numeric" min={0} step={1000} value={income}
                placeholder="e.g. 150000" onChange={(e) => setIncome(e.target.value)} />
              <span>{Number(income) > 0 ? '₹' + rupees(Number(income)) : 'rupees'}</span>
            </div>
          </div>
        </div>
        {fromCheck ? (
          <p className="hint">Price is from your last check. Your salary is not saved.</p>
        ) : (
          <p className="hint">
            Type a price, or <button type="button" className="link-button" onClick={() => go('check')}>check a price</button> first.
          </p>
        )}
      </div>

      {price > 0 && (
        <div className="emi-layout">
          <EmiCalculator price={price} plan={plan} setPlan={setPlan} />
          <EmiAdvice price={price} plan={plan} setPlan={setPlan} income={Number(income)} />
        </div>
      )}
    </>
  )
}

// RBI caps how much of a home's price a bank can lend (the loan-to-value
// ratio): 90% up to ₹30 Lakh, 80% up to ₹75 Lakh, 75% above that
function maxLoanShare(priceLakhs) {
  if (priceLakhs <= 30) return 0.9
  if (priceLakhs <= 75) return 0.8
  return 0.75
}

const LENGTHS = [10, 15, 20, 25, 30]
const COMFORT = 0.3 // EMI within 30% of take-home pay is comfortable
const STRETCH = 0.4 // above 40% leaves little for savings and emergencies

function EmiAdvice({ price, plan, setPlan, income }) {
  const minDown = Math.round((1 - maxLoanShare(price)) * 100)
  const loan = price * 100000 * (1 - plan.down / 100)

  const rows = LENGTHS.map((years) => {
    const emi = emiFor(loan, plan.rate, years)
    return { years, emi, interest: emi * years * 12 - loan, share: income > 0 ? emi / income : null }
  })

  // the best plan: the shortest loan whose EMI is comfortable, because a
  // shorter loan pays far less interest in total
  let best = null
  let verdict = null
  if (income > 0) {
    best = rows.find((r) => r.share <= COMFORT)
    if (best) {
      verdict = { kind: 'good', text: 'Best: ' + best.years + ' years. EMI ₹' + rupees(best.emi) + ', which is ' + Math.round(best.share * 100) + '% of your salary.' }
    } else {
      best = rows.find((r) => r.share <= STRETCH)
      verdict = best
        ? { kind: 'warn', text: 'Tight. ' + best.years + ' years: EMI is ' + Math.round(best.share * 100) + '% of your salary. Pay more down to make it easier.' }
        : { kind: 'bad', text: 'Too costly. Even 30 years takes ' + Math.round(rows[rows.length - 1].share * 100) + '% of your salary. You need about ₹' + rupees(Math.ceil(rows[2].emi / COMFORT / 1000) * 1000) + ' a month, or a cheaper flat.' }
    }
  }


  return (
    <section className="panel">
      <h3>Best plan for you</h3>

      {plan.down < minDown ? (
        <div className="notice notice-bad">
          Pay at least {minDown}% yourself ({money(price * minDown / 100)}). Banks will not lend more.
        </div>
      ) : (
        <div className="notice notice-good">
          Down payment is OK. Keep extra money for registration.
        </div>
      )}

      {verdict ? (
        <div className={'notice notice-' + verdict.kind}>{verdict.text}</div>
      ) : (
        <p className="hint">Add your salary to see the best plan.</p>
      )}

      <details className="emi-more">
      <summary>Compare loan years</summary>
      <table className="area-table emi-table">
        <thead>
          <tr>
            <th scope="col">Loan length</th>
            <th scope="col" className="num">EMI</th>
            <th scope="col" className="num">Interest</th>
            {income > 0 && <th scope="col" className="num">Of salary</th>}
            <th scope="col"><span className="visually-hidden">Use</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.years} className={best?.years === r.years ? 'is-best' : undefined}>
              <th scope="row">{r.years} years{best?.years === r.years && <small>Best</small>}</th>
              <td className="num">₹{rupees(r.emi)}</td>
              <td className="num">{money(r.interest / 100000)}</td>
              {income > 0 && (
                <td className={'num ' + (r.share <= COMFORT ? 'share-ok' : r.share <= STRETCH ? 'share-tight' : 'share-high')}>
                  {Math.round(r.share * 100)}%
                </td>
              )}
              <td>
                {plan.years === r.years
                  ? <span className="hint">In use</span>
                  : <button type="button" className="link-button" onClick={() => setPlan((p) => ({ ...p, years: r.years }))}>Use</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">Longer loan: smaller EMI, but more interest.</p>
      </details>

      <p className="hint">Only a guide. Your bank decides the final loan.</p>
    </section>
  )
}
