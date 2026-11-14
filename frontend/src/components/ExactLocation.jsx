import { useState } from 'react'
import { api } from '../api.js'

// Finds the flat's exact spot from a society name, landmark or Google Maps
// link, so nearby places are measured from there.
export default function ExactLocation({ flat, exactPoint, setExactPoint }) {
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  async function find() {
    if (!query.trim()) return
    setBusy(true)
    setMessage(null)
    try {
      const spot = await api.locate(query, flat.location)
      setExactPoint({ ...spot, area: flat.location })
      setMessage(spot.far_from_area
        ? { kind: 'warn', text: 'Found ' + spot.label + '. It is ' + Math.round(spot.km_from_area_centre) + ' km from ' + flat.location + '. Is the area right?' }
        : { kind: 'good', text: 'Found ' + spot.label + '.' })
    } catch (err) {
      setMessage({ kind: 'bad', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="exact">
      <label htmlFor="exact-query">Society name or Google Maps link <span className="optional">optional</span></label>
      <div className="row-actions">
        <input
          id="exact-query"
          value={query}
          placeholder="e.g. Prestige Lakeside Habitat"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              find()
            }
          }}
        />
        <button type="button" className="button button-quiet" onClick={find} disabled={busy}>
          {busy ? 'Finding…' : 'Find'}
        </button>
      </div>
      {message && <div className={'notice notice-' + message.kind}>{message.text}</div>}
      {exactPoint && exactPoint.area === flat.location && (
        <button type="button" className="link-button" onClick={() => {
          setExactPoint(null)
          setMessage(null)
        }}>
          Use the area centre instead
        </button>
      )}
    </div>
  )
}
