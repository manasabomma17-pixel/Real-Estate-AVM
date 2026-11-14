import { money, rupees } from '../format.js'

// Home loan EMI with the standard formula: P × r × (1+r)^n / ((1+r)^n − 1)
// where P is the loan, r the monthly interest rate and n the number of months.
export function emiFor(loanRupees, ratePercent, years) {
  if (loanRupees <= 0) return 0
  const r = ratePercent / 12 / 100
  const n = years * 12
  const growth = (1 + r) ** n
  return (loanRupees * r * growth) / (growth - 1)
}

export default function EmiCalculator({ price, plan, setPlan }) {
  const { down, rate, years } = plan
  const loan = price * 100000 * (1 - down / 100)
  const emi = emiFor(loan, rate, years)
  const interest = emi * years * 12 - loan
  const set = (field) => (value) => setPlan((p) => ({ ...p, [field]: value }))

  return (
    <section className="panel">
      <p className="emi-figure">
        ₹{rupees(emi)}<small> per month</small>
      </p>
      <p className="hint">Loan {money(loan / 100000)}. Interest {money(interest / 100000)}.</p>
      <Slider label="Down payment" value={down} min={0} max={90} step={5} unit="%" onChange={set('down')} />
      <Slider label="Interest" value={rate} min={6} max={14} step={0.1} unit="%" onChange={set('rate')} />
      <Slider label="Years" value={years} min={5} max={30} step={1} unit="" onChange={set('years')} />
    </section>
  )
}

function Slider({ label, value, unit, onChange, ...limits }) {
  return (
    <label className="slider">
      <span>{label} <strong>{value}{unit}</strong></span>
      <input type="range" value={value} onChange={(e) => onChange(Number(e.target.value))} {...limits} />
    </label>
  )
}
