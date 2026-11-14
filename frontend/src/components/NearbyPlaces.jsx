import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { distance } from '../format.js'
import PlacesMap from './PlacesMap.jsx'

export const GROUPS = [
  { id: 'school', title: 'Schools', colour: '#3B6FB6' },
  { id: 'hospital', title: 'Hospitals', colour: '#A9472D' },
  { id: 'transit', title: 'Bus, metro, train', colour: '#3E7A57' },
]

// The 5 nearest named schools, hospitals and transit stops from
// OpenStreetMap, from the exact spot if the user gave one, otherwise from
// the centre of the area.
export default function NearbyPlaces({ area, exactPoint }) {
  const [data, setData] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let current = true
    setFailed(false)
    api.places(area, exactPoint)
      .then((body) => current && setData(body))
      .catch(() => current && setFailed(true))
    return () => {
      current = false
    }
  }, [area, exactPoint])

  if (failed) return null
  if (!data) return <section className="panel panel-wide places is-loading" aria-busy="true" />

  const empty = GROUPS.every((g) => data.places[g.id].length === 0)

  return (
    <section className="panel panel-wide places">
      <p className="places-basis">
        {data.exact
          ? 'From the place you gave.'
          : 'From the centre of ' + area + '.'}
      </p>
      {empty ? (
        <p>Nothing found within 3 km.</p>
      ) : (
        <div className="places-body">
          <div className="places-lists">
            {GROUPS.map((group) => (
              <div key={group.id} className="places-group">
                <h4><i style={{ background: group.colour }} />{group.title}</h4>
                {data.places[group.id].length === 0 ? (
                  <p className="hint">None within 3 km</p>
                ) : (
                  <ol>
                    {data.places[group.id].map((place) => (
                      <li key={place.name + place.km}>
                        <span>{place.name}{group.id === 'transit' && place.type ? <small> {place.type}</small> : null}</span>
                        <span className="places-km">{distance(place.km)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            ))}
          </div>
          <PlacesMap centre={data.centre} exact={data.exact} places={data.places} />
        </div>
      )}
    </section>
  )
}
