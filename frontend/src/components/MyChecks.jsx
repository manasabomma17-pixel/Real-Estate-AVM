import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { money, shortDate, VERDICT_KIND, VERDICT_WORDS } from '../format.js'

// "My checks": every price check the user made, newest first. Saved on the
// server, so it shows on any phone or laptop the user logs in from.
export default function MyChecks({ setFlat, go }) {
  const [checks, setChecks] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.myChecks().then((body) => setChecks(body.checks)).catch((err) => setError(err.message))
  }, [])

  async function remove(id) {
    try {
      await api.deleteCheck(id)
      setChecks((old) => old.filter((c) => c.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  function openAgain(c) {
    setFlat({
      location: c.location, size_sqft: c.size_sqft, bedrooms: c.bedrooms, bathrooms: c.bathrooms,
      asking_price: c.asking_price ?? '', building_age: c.building_age ?? '',
      under_construction: Boolean(c.under_construction),
    })
    go('check')
  }

  return (
    <>
      <section className="intro">
        <h1>My checks</h1>
        <p className="lede">Your past price checks. Open one to check it again.</p>
      </section>

      {error && <div className="notice notice-bad" role="alert">{error}</div>}
      {!checks && !error && <p className="hint" role="status">Loading…</p>}
      {checks && checks.length === 0 && (
        <div className="sheet empty">
          <p>No checks yet.</p>
          <button type="button" className="button button-primary" onClick={() => go('check')}>Check a price</button>
        </div>
      )}

      {checks && checks.length > 0 && (
        <ul className="check-list">
          {checks.map((c) => (
            <li key={c.id} className="sheet check-item">
              <div className="check-main">
                <p className="check-flat">{c.bedrooms} BHK, {Math.round(c.size_sqft)} sqft in {c.location}</p>
                <p className="hint">{shortDate(c.created_at)}</p>
              </div>
              <dl className="check-numbers">
                <div><dt>Our price</dt><dd>{money(c.today_price, 2)}</dd></div>
                <div><dt>Seller asked</dt><dd>{c.asking_price ? money(c.asking_price, 2) : '–'}</dd></div>
                <div>
                  <dt>Verdict</dt>
                  <dd>{c.verdict ? <span className={'tag tag-' + VERDICT_KIND[c.verdict]}>{VERDICT_WORDS[c.verdict]}</span> : '–'}</dd>
                </div>
              </dl>
              <div className="row-actions">
                <button type="button" className="button button-quiet" onClick={() => openAgain(c)}>Check again</button>
                <button type="button" className="link-button" onClick={() => remove(c.id)}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
