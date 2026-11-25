import { useState } from 'react'
import { api } from '../api.js'
import { money, rupees, VERDICT_KIND, VERDICT_WORDS } from '../format.js'
import AreaPicker from './AreaPicker.jsx'

// Two flats side by side: our price for each, and which one is the better deal.
const EMPTY = { location: '', size_sqft: 1000, bedrooms: 2, bathrooms: 2, asking: '', unit: 'L' }

const lakhsOf = (f) => (Number(f.asking) > 0 ? Number(f.asking) * (f.unit === 'Cr' ? 100 : 1) : 0)

export default function TwoFlats({ areas, flat }) {
  const [flats, setFlats] = useState(() => [
    {
      ...EMPTY, location: flat.location, size_sqft: flat.size_sqft, bedrooms: flat.bedrooms, bathrooms: flat.bathrooms,
      asking: flat.asking_price >= 100 ? +(flat.asking_price / 100).toFixed(4) : flat.asking_price || '',
      unit: flat.asking_price >= 100 ? 'Cr' : 'L',
    },
    { ...EMPTY },
  ])
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const update = (i, field, value) => {
    setFlats((old) => old.map((f, j) => (j === i ? { ...f, [field]: value } : f)))
    setResults(null)
  }

  async function compare(event) {
    event.preventDefault()
    if (flats.some((f) => !areas.some((a) => a.name === f.location))) {
      setError('Pick an area from the list for both flats.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      const answers = await Promise.all(flats.map((f) => {
        const body = { location: f.location, size_sqft: Number(f.size_sqft), bedrooms: Number(f.bedrooms),
          bathrooms: Number(f.bathrooms) }
        if (lakhsOf(f) > 0) body.asking_price = lakhsOf(f)
        return api.predict(body)
      }))
      setResults(answers)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <section className="intro">
        <h1>Two flats</h1>
        <p className="lede">Enter two flats. We show our price for each and which is the better deal.</p>
      </section>

      <form className="two-flats" onSubmit={compare}>
        {flats.map((f, i) => (
          <fieldset key={i} className="sheet form">
            <legend>Flat {i === 0 ? 'A' : 'B'}</legend>
            <div className="field">
              <label htmlFor={'area-' + i}>Area</label>
              <AreaPicker id={'area-' + i} areas={areas} value={f.location} onChange={(name) => update(i, 'location', name)} />
            </div>
            <div className="field-grid">
              <NumberBox id={"size-" + i} label="Size" unit="sqft" value={f.size_sqft} min={200} step={50} onChange={(v) => update(i, 'size_sqft', v)} />
              <NumberBox id={"bhk-" + i} label="Bedrooms" unit="BHK" value={f.bedrooms} min={1} max={10} onChange={(v) => update(i, 'bedrooms', v)} />
              <NumberBox id={"bath-" + i} label="Bathrooms" value={f.bathrooms} min={1} max={10} onChange={(v) => update(i, 'bathrooms', v)} />
            </div>
            <div className="field">
              <label htmlFor={'asking-' + i}>Seller’s price <span className="optional">optional</span></label>
              <div className="input-unit">
                <input id={'asking-' + i} type="number" inputMode="decimal" min={0} step="any" value={f.asking}
                  placeholder={f.unit === 'Cr' ? 'e.g. 1.2' : 'e.g. 95'} onChange={(e) => update(i, 'asking', e.target.value)} />
                <div className="unit-switch" role="group" aria-label={'Unit of flat ' + (i ? 'B' : 'A') + ' price'}>
                  {[['L', 'Lakhs'], ['Cr', 'Crore']].map(([id, label]) => (
                    <button key={id} type="button" aria-pressed={f.unit === id} onClick={() => update(i, 'unit', id)}>{label}</button>
                  ))}
                </div>
              </div>
              {lakhsOf(f) > 0 && <p className="hint">= {money(lakhsOf(f), 2)}</p>}
            </div>
          </fieldset>
        ))}
        <div className="two-flats-actions">
          <button className="button button-primary" type="submit" disabled={busy || !areas.length}>
            {busy ? 'Checking…' : 'Compare'}
          </button>
          {error && <div className="notice notice-bad" role="alert">{error}</div>}
        </div>
      </form>

      {results && <Result flats={flats} results={results} />}
    </>
  )
}

function NumberBox({ id, label, unit, value, onChange, ...limits }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="input-unit">
        <input id={id} type="number" inputMode="numeric" value={value} {...limits} onChange={(e) => onChange(e.target.value)} />
        {unit && <span>{unit}</span>}
      </div>
    </div>
  )
}

// a seller's price under 30% or over 3x our price is almost always a typo
const typo = (asking, today) => asking > 0 && (asking < today * 0.3 || asking > today * 3)

function Result({ flats, results }) {
  const names = ['Flat A', 'Flat B']
  const asks = flats.map(lakhsOf)
  const judged = results.map((r, i) => asks[i] > 0 && !typo(asks[i], r.today_price))

  let winner
  if (judged[0] && judged[1]) {
    const gaps = results.map((r) => r.difference_percent)
    const best = gaps[0] <= gaps[1] ? 0 : 1
    const describe = (g) => Math.round(Math.abs(g)) + '% ' + (g >= 0 ? 'more' : 'less')
    winner = gaps[0] === gaps[1]
      ? 'Both are equally priced compared with our price.'
      : names[best] + ' is the better deal. Its seller asks ' + describe(gaps[best]) + ' than our price; '
        + names[1 - best] + '’s seller asks ' + describe(gaps[1 - best]) + '.'
  } else {
    const rates = results.map((r) => r.today_price_per_sqft)
    const cheaper = rates[0] <= rates[1] ? 0 : 1
    winner = names[cheaper] + ' costs ₹' + rupees(Math.abs(rates[0] - rates[1])) + ' less per sqft by our price. '
      + 'Add both sellers’ prices to see which is the better deal.'
  }

  return (
    <section className="result" aria-live="polite">
      <div className="verdict">
        <h2 className="verdict-title two-flats-title">{winner}</h2>
      </div>
      <div className="table-wrap">
        <table className="two-flats-table">
          <thead>
            <tr><th scope="col"></th>{names.map((n) => <th key={n} scope="col">{n}</th>)}</tr>
          </thead>
          <tbody>
            <tr><th scope="row">Flat</th>{flats.map((f, i) => <td key={i}>{f.bedrooms} BHK, {f.size_sqft} sqft, {f.location}</td>)}</tr>
            <tr><th scope="row">Our price</th>{results.map((r, i) => <td key={i}><strong>{money(r.today_price, 2)}</strong></td>)}</tr>
            <tr><th scope="row">Likely range</th>{results.map((r, i) => <td key={i}>{money(r.today_low)} to {money(r.today_high)}</td>)}</tr>
            <tr><th scope="row">Per sqft</th>{results.map((r, i) => <td key={i}>₹{rupees(r.today_price_per_sqft)}</td>)}</tr>
            <tr><th scope="row">Seller asks</th>{asks.map((a, i) => <td key={i}>{a > 0 ? money(a, 2) : '–'}</td>)}</tr>
            <tr>
              <th scope="row">Verdict</th>
              {results.map((r, i) => (
                <td key={i}>
                  {typo(asks[i], r.today_price) ? 'Check the price (Lakhs or Crore?)'
                    : judged[i] ? <span className={'tag tag-' + VERDICT_KIND[r.verdict]}>{VERDICT_WORDS[r.verdict]}, {r.difference_percent > 0 ? '+' : ''}{Math.round(r.difference_percent)}%</span>
                      : '–'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}
