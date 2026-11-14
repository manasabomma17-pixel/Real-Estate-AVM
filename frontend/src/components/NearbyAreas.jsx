import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { distance, rupees } from '../format.js'
import AreaPicker from './AreaPicker.jsx'

// The 10 closest areas with enough records, and how their typical price per
// sqft today compares. Useful when the chosen area is over budget.
export default function NearbyAreas({ areas, flat, setFlat, go }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let current = true
    setError(null)
    api.nearbyAreas(flat.location)
      .then((body) => current && setData(body))
      .catch((err) => current && setError(err.message))
    return () => {
      current = false
    }
  }, [flat.location])

  const widest = data ? Math.max(20, ...data.areas.map((a) => Math.abs(a.difference_percent ?? 0))) : 1

  const checkHere = (name) => {
    setFlat((old) => ({ ...old, location: name }))
    go('check')
  }

  return (
    <>
      <section className="intro">
        <h1>Other areas nearby</h1>
        <p className="lede">Cheaper or costlier areas close to {flat.location}.</p>
      </section>

      <div className="toolbar">
        <div className="field">
          <label htmlFor="area-NearbyAreas">Area</label>
          <AreaPicker id="area-NearbyAreas" areas={areas} value={flat.location} onChange={(name) => setFlat((o) => ({ ...o, location: name }))} />
        </div>
        {data?.rate_today && (
          <p className="toolbar-note">
            {flat.location}: <strong>₹{rupees(data.rate_today)}</strong> per sqft
          </p>
        )}
      </div>

      {error && <div className="notice notice-bad">{error}</div>}
      {data && (
        <section className="panel panel-wide">
          <table className="area-table">
            <thead>
              <tr>
                <th scope="col">Area</th>
                <th scope="col" className="num">Distance</th>
                <th scope="col" className="num">Per sqft</th>
                <th scope="col">Compared</th>
                <th scope="col"><span className="visually-hidden">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {data.areas.map((a) => {
                const d = a.difference_percent
                const tone = d == null ? '' : d < -5 ? 'is-cheaper' : d > 5 ? 'is-pricier' : 'is-same'
                return (
                  <tr key={a.name}>
                    <th scope="row">{a.name}</th>
                    <td className="num">{distance(a.km)}</td>
                    <td className="num">{a.rate_today ? '₹' + rupees(a.rate_today) : '–'}</td>
                    <td>
                      {d == null ? '–' : (
                        <span className={'diff ' + tone}>
                          <span className="diff-track">
                            <span className="diff-bar" style={{ width: (Math.abs(d) / widest) * 50 + '%', [d < 0 ? 'right' : 'left']: '50%' }} />
                          </span>
                          <span className="diff-text">
                            {Math.abs(d) <= 5 ? 'Same' : Math.abs(d) + '% ' + (d < 0 ? 'cheaper' : 'costlier')}
                          </span>
                        </span>
                      )}
                    </td>
                    <td><button type="button" className="link-button" onClick={() => checkHere(a.name)}>Check here</button></td>
                  </tr>
                )
              })}
            </tbody>
          </table>

        </section>
      )}
    </>
  )
}
