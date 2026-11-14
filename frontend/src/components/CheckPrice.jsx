import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { money, rupees } from '../format.js'
import AreaPicker from './AreaPicker.jsx'
import PriceScale from './PriceScale.jsx'
import PriceWaterfall from './PriceWaterfall.jsx'
import Suggestions from './Suggestions.jsx'

const EXAMPLE = '2 BHK Flat for sale in Whitefield, Bangalore. 1,200 sq.ft, 2 bathrooms. Price: Rs 1.75 Cr'

export default function CheckPrice({ areas, flat, setFlat, exactPoint, setExactPoint, check, setCheck, go }) {
  const [listing, setListing] = useState('')
  const [listingNote, setListingNote] = useState(null)
  const [reading, setReading] = useState(false)

  const [summary, setSummary] = useState(null)
  const [checking, setChecking] = useState(false)
  const [slowServer, setSlowServer] = useState(false)
  const [error, setError] = useState(null)

  const update = (field, value) => setFlat((old) => ({ ...old, [field]: value }))

  // the asking price can be typed in Lakhs or Crore; it is kept in Lakhs
  const [unit, setUnit] = useState('L')
  const [askingText, setAskingText] = useState('')
  const toLakhs = (text, u) => (Number(text) > 0 ? Number(text) * (u === 'Cr' ? 100 : 1) : '')
  const setAsking = (lakhs) => {
    const useCrore = lakhs >= 100
    setUnit(useCrore ? 'Cr' : 'L')
    setAskingText(lakhs ? String(useCrore ? +(lakhs / 100).toFixed(4) : lakhs) : '')
    update('asking_price', lakhs || '')
  }

  // real numbers about the chosen area, refreshed when the area or BHK changes
  useEffect(() => {
    if (!flat.location || !areas.some((a) => a.name === flat.location)) return
    let current = true
    api.summary(flat.location, Number(flat.bedrooms) || 2)
      .then((body) => current && setSummary(body))
      .catch(() => current && setSummary(null))
    return () => {
      current = false
    }
  }, [flat.location, flat.bedrooms, areas])

  async function readListing() {
    if (!listing.trim()) {
      setListingNote({ kind: 'warn', text: 'Paste the ad text first.' })
      return
    }
    setReading(true)
    try {
      const { found, missing, is_link: isLink, building_age: age, under_construction: building } = await api.parseListing(listing)
      const filled = {}
      if (found.location) filled.location = found.location
      if (found.bedrooms) filled.bedrooms = found.bedrooms
      if (found.bathrooms) filled.bathrooms = found.bathrooms
      if (found.size_sqft) filled.size_sqft = found.size_sqft
      if (found.asking_price) setAsking(found.asking_price)
      const foundCount = Object.keys(filled).length + (found.asking_price ? 1 : 0)
      if (building) filled.under_construction = true
      if (age != null) Object.assign(filled, { building_age: age, under_construction: false })
      setFlat((old) => ({ ...old, ...filled }))
      const names = { location: 'area', bedrooms: 'bedrooms', bathrooms: 'bathrooms', size_sqft: 'size', asking_price: 'price' }
      setListingNote({
        kind: missing.length ? 'warn' : 'good',
        found: foundCount,
        age: building ? 'under construction' : age != null ? age + ' years old' : null,
        missing: missing.map((m) => names[m]),
        isLink,
      })
    } catch (err) {
      setListingNote({ kind: 'bad', text: err.message })
    } finally {
      setReading(false)
    }
  }

  async function checkPrice(event, askingOverride) {
    event?.preventDefault()
    setError(null)
    setChecking(true)
    const slowTimer = setTimeout(() => setSlowServer(true), 4000)
    const priced = {
      location: flat.location,
      size_sqft: Number(flat.size_sqft),
      bedrooms: Number(flat.bedrooms),
      bathrooms: Number(flat.bathrooms),
    }
    const asking = askingOverride ?? Number(flat.asking_price)
    if (asking > 0) priced.asking_price = asking
    const point = exactPoint && exactPoint.area === flat.location ? exactPoint : null
    try {
      const result = await api.predict(priced)
      // an asking price under 30% or over 3 times our estimate is almost
      // always a typo (Lakhs typed as Crore, or the other way), so it is not
      // judged; the advice is then worked out without it
      const typo = asking > 0 && (asking < result.today_price * 0.3 || asking > result.today_price * 3)
      const { asking_price: _, ...withoutAsking } = priced
      const age = {
        building_age: flat.under_construction || flat.building_age === '' ? null : Number(flat.building_age),
        under_construction: Boolean(flat.under_construction),
      }
      const advice = await api.advice({ ...(typo ? withoutAsking : priced), ...age }, point)
      setCheck({ flat: { ...priced, ...age }, result, suggestions: advice.suggestions, typo, age: advice.age })
      requestAnimationFrame(() => document.getElementById('result')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (err) {
      setError(err.message)
    } finally {
      clearTimeout(slowTimer)
      setSlowServer(false)
      setChecking(false)
    }
  }

  const result = check?.result
  // the shown result belongs to an earlier version of the form
  const stale = check && (check.flat.location !== flat.location || check.flat.size_sqft !== Number(flat.size_sqft)
    || check.flat.bedrooms !== Number(flat.bedrooms) || check.flat.bathrooms !== Number(flat.bathrooms)
    || (check.flat.asking_price ?? 0) !== (Number(flat.asking_price) || 0)
    || check.flat.under_construction !== Boolean(flat.under_construction)
    || (check.flat.building_age ?? '') !== (flat.under_construction || flat.building_age === '' ? '' : Number(flat.building_age)))

  return (
    <>
      <section className="intro">
        <h1>Is the price fair?</h1>
        <p className="lede">Enter the flat details. We tell you a fair price.</p>
      </section>

      <div className="check-layout">
        <form className="sheet form" onSubmit={checkPrice}>
          <div className="field">
            <label htmlFor="listing">Paste the ad <span className="optional">optional</span></label>
            <textarea
              id="listing"
              rows={3}
              value={listing}
              placeholder={EXAMPLE}
              onChange={(event) => setListing(event.target.value)}
            />
            <div className="row-actions">
              <button type="button" className="button button-quiet" onClick={readListing} disabled={reading}>
                {reading ? 'Reading…' : 'Fill from ad'}
              </button>
              {!listing && (
                <button type="button" className="link-button" onClick={() => setListing(EXAMPLE)}>
                  Try an example
                </button>
              )}
            </div>
            {listingNote && <ListingNote note={listingNote} />}
          </div>

          <div className="field">
            <label htmlFor="area-CheckPrice">Area</label>
            <AreaPicker id="area-CheckPrice" areas={areas} value={flat.location} onChange={(name) => update('location', name)} />
            <AreaLine summary={summary} />
          </div>

          <div className="field-grid">
            <NumberField label="Size" unit="sqft" value={flat.size_sqft} min={200} step={50} onChange={(v) => update('size_sqft', v)} />
            <NumberField label="Bedrooms" unit="BHK" value={flat.bedrooms} min={1} max={10} onChange={(v) => update('bedrooms', v)} />
            <NumberField label="Bathrooms" value={flat.bathrooms} min={1} max={10} onChange={(v) => update('bathrooms', v)} />
          </div>

          <div className="field">
            <label htmlFor="age">How old is the building? <span className="optional">optional</span></label>
            <div className="age-row">
              <div className="input-unit">
                <input id="age" type="number" inputMode="numeric" min={0} max={100} value={flat.building_age}
                  placeholder="e.g. 8" disabled={flat.under_construction}
                  onChange={(event) => update('building_age', event.target.value)} />
                <span>years old</span>
              </div>
              <label className="check-inline">
                <input type="checkbox" checked={flat.under_construction}
                  onChange={(event) => update('under_construction', event.target.checked)} />
                Still being built
              </label>
            </div>
          </div>

          <div className="field">
            <label htmlFor="asking">Seller’s price <span className="optional">optional</span></label>
            <div className="input-unit">
              <input
                id="asking"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={askingText}
                placeholder={unit === 'Cr' ? 'e.g. 1.75' : 'e.g. 85'}
                onChange={(event) => {
                  setAskingText(event.target.value)
                  update('asking_price', toLakhs(event.target.value, unit))
                }}
              />
              <div className="unit-switch" role="group" aria-label="Unit of the asking price">
                {[['L', 'Lakhs'], ['Cr', 'Crore']].map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={unit === id}
                    onClick={() => {
                      setUnit(id)
                      update('asking_price', toLakhs(askingText, id))
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {Number(flat.asking_price) > 0 && (
              <p className="hint">= {money(Number(flat.asking_price), 2)}</p>
            )}
          </div>

          <button className="button button-primary button-wide" type="submit" disabled={checking || !areas.length}>
            {checking ? 'Checking…' : 'Check price'}
          </button>
          {slowServer && (
            <p className="hint" role="status">Starting up. The first check can take up to 1 minute.</p>
          )}
          {error && <div className="notice notice-bad" role="alert">{error}</div>}
        </form>

      </div>

      {result && (
        <section id="result" className={'result' + (stale ? ' is-stale' : '')} aria-live="polite">
          {stale && (
            <div className="notice notice-warn">
              You changed the details. Press <strong>Check price</strong> again.
            </div>
          )}
          {check.typo ? (
            <TypoCheck
              flat={check.flat}
              result={result}
              onFix={(lakhs) => {
                setAsking(lakhs)
                checkPrice(null, lakhs)
              }}
            />
          ) : (
            <Verdict flat={check.flat} result={result} />
          )}
          <PriceScale estimate={result.today_price} asking={check.typo ? null : check.flat.asking_price} />
          <EstimateFacts flat={check.flat} result={result} summary={summary} />
          {check.age && <AgeNote age={check.age} />}
          {result.warnings.map((w) => (
            <div key={w} className="notice notice-warn">{w}</div>
          ))}

          <Suggestions items={check.suggestions} />
          <details className="more-box">
            <summary>Why this price?</summary>
            <PriceWaterfall result={result} />
          </details>

          <div className="result-footer">
            <button type="button" className="button button-quiet" onClick={() => go('compare')}>
              Compare
            </button>
            <button type="button" className="button button-quiet" onClick={() => go('places')}>
              Places nearby
            </button>
            <button type="button" className="button button-quiet" onClick={() => go('checklist')}>
              Before you buy
            </button>
            <button type="button" className="button button-quiet" onClick={() => go('emi')}>
              Loan EMI
            </button>
            <button type="button" className="button button-quiet" onClick={() => downloadSummary(check)}>
              Download
            </button>
          </div>
        </section>
      )}

    </>
  )
}

function NumberField({ label, unit, value, onChange, ...limits }) {
  return (
    <div className="field">
      <label className="stack">
        {label}
        <div className="input-unit">
          <input type="number" inputMode="numeric" value={value} onChange={(e) => onChange(e.target.value)} required {...limits} />
          {unit && <span>{unit}</span>}
        </div>
      </label>
    </div>
  )
}

function ListingNote({ note }) {
  if (note.text) return <div className={'notice notice-' + note.kind}>{note.text}</div>
  return (
    <div className={'notice notice-' + note.kind}>
      {note.found > 0 ? <>Filled {note.found} of 5{note.age && ', and building age'}. Please check.</> : <>Could not read the ad.</>}
      {note.missing.length > 0 && <> Please add: {note.missing.join(', ')}.</>}
      {note.isLink && <p>Links do not work. Copy the text of the ad and paste it here.</p>}
    </div>
  )
}


// one line about the chosen area under the Area box
function AreaLine({ summary }) {
  if (!summary) return null
  if (!summary.records) return <p className="hint">Few records here. Our price may be less accurate.</p>
  return <p className="hint">Usual price here: <strong>₹{rupees(summary.typical_rate_today)} per sqft</strong></p>
}

// shown instead of a verdict when the asking price is too far from our
// estimate to be real, which nearly always means Lakhs and Crore got mixed up
function TypoCheck({ flat, result, onFix }) {
  const asking = flat.asking_price
  const guesses = [asking * 100, asking / 100].filter((g) => g >= result.today_price * 0.3 && g <= result.today_price * 3)
  const guess = guesses[0]
  return (
    <div className="verdict verdict-warn">
      <h2 className="verdict-title">Check the seller’s price</h2>
      <p>
        {money(asking, 2)} is too {asking < result.today_price ? 'low' : 'high'} for this flat.
        {guess ? ' Did you mean ' + money(guess, 2) + '?' : ' Check the number and Lakhs or Crore.'}
      </p>
      {guess && (
        <div className="row-actions">
          <button type="button" className="button button-primary" onClick={() => onFix(guess)}>
            Yes, {money(guess, 2)}
          </button>
        </div>
      )}
    </div>
  )
}

// building age: a rough guide shown apart from the model's estimate, because
// our training data has no building age, so the model cannot learn its effect
// (standard valuer rule: a building lasts about 60 years; land does not wear out)
function AgeNote({ age }) {
  return (
    <div className="age-note">
      <strong>{age.years}-year-old building: about {money(age.adjusted_price, 2)}</strong>
      <span className="hint">Old buildings are worth a little less. This is a rough guide.</span>
    </div>
  )
}

const VERDICT_TONE = { 'Looks overpriced': 'bad', 'Looks underpriced': 'warn', 'Looks fairly priced': 'good' }
const VERDICT_TEXT = { 'Looks overpriced': 'Price is too high', 'Looks underpriced': 'Price is low. Find out why.', 'Looks fairly priced': 'Price is fair' }

function Verdict({ flat, result }) {
  if (!result.verdict) {
    return (
      <div className="verdict">
        <p className="verdict-kicker">{flat.bedrooms} BHK in {flat.location}</p>
        <h2 className="verdict-title">Fair price: about {money(result.today_price)}</h2>
        <p>Add the seller’s price to check it.</p>
      </div>
    )
  }
  const tone = VERDICT_TONE[result.verdict]
  const diff = result.difference_percent
  return (
    <div className={'verdict verdict-' + tone}>
      <p className="verdict-kicker">{flat.bedrooms} BHK in {flat.location}, seller asks {money(flat.asking_price)}</p>
      <h2 className="verdict-title">{VERDICT_TEXT[result.verdict]}</h2>
      <p>Seller asks {Math.round(Math.abs(diff))}% {diff >= 0 ? 'more' : 'less'} than our price of {money(result.today_price)}.</p>
    </div>
  )
}

function EstimateFacts({ flat, result, summary }) {
  const typical = summary?.area === flat.location ? summary.typical_bhk_price_today : null
  return (
    <dl className="facts facts-wide">
      <div>
        <dt>Our price</dt>
        <dd>{money(result.today_price, 2)}</dd>
      </div>
      <div>
        <dt>Per sqft</dt>
        <dd>₹{rupees(result.today_price_per_sqft)}</dd>
      </div>
      {typical != null && (
        <div>
          <dt>Usual {flat.bedrooms} BHK here</dt>
          <dd>{money(typical)}</dd>
        </div>
      )}
    </dl>
  )
}

function downloadSummary(check) {
  const { flat, result, suggestions } = check
  const lines = [
    'Real Estate AVM: Bangalore flat price check',
    '',
    'Flat: ' + flat.bedrooms + ' BHK, ' + flat.bathrooms + ' bathrooms, ' + flat.size_sqft + ' sqft in ' + flat.location,
    flat.asking_price ? 'Asking price: ' + money(flat.asking_price) : null,
    'Estimate today: ' + money(result.today_price, 2) + ' (likely ' + money(result.today_low) + ' to ' + money(result.today_high) + ')',
    flat.under_construction ? 'Building: under construction' : flat.building_age != null ? 'Building age: ' + flat.building_age + ' years' : null,
    check.age ? 'Rough age-adjusted price: ' + money(check.age.adjusted_price, 2) + ' (building ' + check.age.depreciation_percent + '% depreciated)' : null,
    result.verdict ? 'Verdict: ' + result.verdict + ' (' + result.difference_percent + '%)' : null,
    'Model estimate at 2017-19 prices: ' + result.predicted_price + ' Lakhs, x' + result.market_factor + ' market growth since',
    '',
    'Why this price (starting from ' + result.base_price + ' Lakhs):',
    ...result.factors.map((f) => '  ' + (f.effect >= 0 ? '+' : '') + f.effect + ' L  ' + f.name),
    '',
    'Suggestions:',
    ...suggestions.map((s) => '- ' + s.title + ': ' + s.text),
  ].filter((line) => line !== null)
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain' }))
  link.download = 'price-check-' + flat.location.replace(/\W+/g, '-').toLowerCase() + '.txt'
  link.click()
  URL.revokeObjectURL(link.href)
}
