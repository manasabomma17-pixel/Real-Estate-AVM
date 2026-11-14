import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { rupees } from '../format.js'
import AreaPicker from './AreaPicker.jsx'

const SCOPE_TEXT = {
  area_bhk: (a, b) => b + ' BHK flats in ' + a,
  area: (a) => 'All flats in ' + a,
  city_bhk: (a, b) => b + ' BHK flats in all of Bangalore',
}

// Where a price sits among comparable flats, per sqft so different sizes
// compare fairly. The records are from 2017-19, brought up to today.
export default function Compare({ areas, flat, setFlat, check, go }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const bedrooms = Number(flat.bedrooms) || 2

  useEffect(() => {
    let current = true
    setError(null)
    api.comparison(flat.location, bedrooms)
      .then((body) => current && setData(body))
      .catch((err) => current && setError(err.message))
    return () => {
      current = false
    }
  }, [flat.location, bedrooms])

  // our estimate and the asking price, as rupees per sqft
  const markers = []
  const same = check && check.flat.location === flat.location && check.flat.bedrooms === bedrooms
  if (same) {
    markers.push({ id: 'estimate', label: 'Our price', rate: check.result.today_price_per_sqft })
    if (check.flat.asking_price) markers.push({ id: 'asking', label: 'Seller’s price', rate: (check.flat.asking_price * 100000) / check.flat.size_sqft })
  } else if (Number(flat.asking_price) > 0 && Number(flat.size_sqft) > 0) {
    markers.push({ id: 'asking', label: 'Seller’s price', rate: (Number(flat.asking_price) * 100000) / Number(flat.size_sqft) })
  }

  return (
    <>
      <section className="intro">
        <h1>Compare with other flats</h1>
        <p className="lede">Price per sqft of similar flats.</p>
      </section>

      <div className="toolbar">
        <div className="field">
          <label htmlFor="area-Compare">Area</label>
          <AreaPicker id="area-Compare" areas={areas} value={flat.location} onChange={(name) => setFlat((o) => ({ ...o, location: name }))} />
        </div>
        <div className="field field-narrow">
          <label className="stack">
            Bedrooms
            <select value={bedrooms} onChange={(e) => setFlat((o) => ({ ...o, bedrooms: Number(e.target.value) }))}>
              {[1, 2, 3, 4, 5, 6].map((b) => <option key={b} value={b}>{b} BHK</option>)}
            </select>
          </label>
        </div>
      </div>

      {error && <div className="notice notice-bad">{error}</div>}
      {data && data.count > 0 && (
        <section className="panel panel-wide">
          <dl className="facts facts-wide">
            <div><dt>Usual price</dt><dd>₹{rupees(data.typical)}<small>/sqft</small></dd></div>
            <div><dt>Most flats</dt><dd>₹{rupees(data.middle_half[0])} – {rupees(data.middle_half[1])}</dd></div>
            <div><dt>Flats compared</dt><dd>{data.count}</dd></div>
          </dl>
          <p className="hint">{SCOPE_TEXT[data.scope](flat.location, bedrooms)}</p>
          <Histogram rates={data.rates} markers={markers} />
          <MarkerNotes rates={data.rates} markers={markers} go={go} />
        </section>
      )}

      <div className="notice notice-plain">
        These are old records, not flats for sale.
      </div>
    </>
  )
}

function Histogram({ rates, markers }) {
  const W = 760
  const H = 260
  const L = 44
  const B = 36
  const bins = useMemo(() => makeBins(rates, 22), [rates])
  const lo = bins[0].from
  const hi = bins[bins.length - 1].to
  const most = Math.max(...bins.map((b) => b.count))
  const x = (v) => L + ((Math.min(Math.max(v, lo), hi) - lo) / (hi - lo)) * (W - L - 12)
  const y = (c) => H - B - (c / most) * (H - B - 40)
  const yTicks = niceTicks(most)

  return (
    <figure className="histogram">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={'Histogram of ' + rates.length + ' comparable flats by price per sqft'}>
        {yTicks.map((t) => (
          <g key={t}>
            <line className="grid" x1={L} x2={W - 12} y1={y(t)} y2={y(t)} />
            <text className="axis" x={L - 8} y={y(t) + 4} textAnchor="end">{t}</text>
          </g>
        ))}
        {bins.map((b) => (
          <rect key={b.from} className="bin" x={x(b.from) + 1} y={y(b.count)} width={Math.max(x(b.to) - x(b.from) - 2, 1)} height={H - B - y(b.count)}>
            <title>{b.count} flats at ₹{rupees(b.from)} to {rupees(b.to)} per sqft</title>
          </rect>
        ))}
        {bins.filter((_, i) => i % 4 === 0).map((b) => (
          <text key={'x' + b.from} className="axis" x={x(b.from)} y={H - B + 18} textAnchor="middle">₹{rupees(Math.round(b.from / 100) * 100)}</text>
        ))}
        <text className="axis-title" x={W / 2} y={H - 2} textAnchor="middle">Price per sqft</text>
        {markers.map((m, i) => (
          <g key={m.id} className={'marker marker-' + m.id}>
            <line x1={x(m.rate)} x2={x(m.rate)} y1={24} y2={H - B} />
            <text x={x(m.rate)} y={14 + i * 0} textAnchor={x(m.rate) > W - 120 ? 'end' : x(m.rate) < 120 ? 'start' : 'middle'} dy={i * 12}>
              {m.label}
            </text>
          </g>
        ))}
      </svg>
    </figure>
  )
}

function MarkerNotes({ rates, markers, go }) {
  if (!markers.length) {
    return (
      <p className="hint">
        <button type="button" className="link-button" onClick={() => go('check')}>Check a price</button> to see it on the chart.
      </p>
    )
  }
  return (
    <ul className="marker-notes">
      {markers.map((m) => {
        const below = Math.round((rates.filter((r) => r < m.rate).length / rates.length) * 100)
        let extra = ''
        if (m.id === 'asking' && below > 85) extra = ' Very costly.'
        if (m.id === 'asking' && below < 15) extra = ' Very cheap. Find out why.'
        return (
          <li key={m.id} className={'marker-note-' + m.id}>
            <strong>{m.label}: ₹{rupees(m.rate)} per sqft.</strong> Costlier than {below}% of flats.{extra}
          </li>
        )
      })}
    </ul>
  )
}

function makeBins(values, count) {
  // trim the extreme 2% at each end so one mansion does not squash the chart
  const sorted = [...values].sort((a, b) => a - b)
  const lo = sorted[Math.floor(sorted.length * 0.02)]
  const hi = sorted[Math.ceil(sorted.length * 0.98) - 1]
  const width = Math.max((hi - lo) / count, 1)
  const bins = Array.from({ length: count }, (_, i) => ({ from: lo + i * width, to: lo + (i + 1) * width, count: 0 }))
  for (const v of sorted) {
    const i = Math.min(Math.max(Math.floor((v - lo) / width), 0), count - 1)
    bins[i].count += 1
  }
  return bins
}

function niceTicks(max) {
  const step = [1, 2, 5, 10, 20, 25, 50, 100].find((s) => max / s <= 5) ?? 200
  const ticks = []
  for (let t = 0; t <= max; t += step) ticks.push(t)
  return ticks
}
