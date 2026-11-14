import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { distance } from '../format.js'

const COLOURS = { school: '#3B6FB6', hospital: '#A9472D', transit: '#3E7A57' }
const NAMES = { school: 'School', hospital: 'Hospital or clinic', transit: 'Transit' }

// A small OpenStreetMap map (drawn with Leaflet) with the flat or area
// centre in gold and each nearby place as a coloured dot.
export default function PlacesMap({ centre, exact, places }) {
  const holder = useRef(null)

  useEffect(() => {
    const map = L.map(holder.current, { scrollWheelZoom: false, attributionControl: true })
    // OpenStreetMap's own map tiles: free to use with this credit shown
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)

    const points = [[centre.lat, centre.lon]]
    for (const [group, items] of Object.entries(places)) {
      for (const place of items) {
        if (place.lat == null) continue
        points.push([place.lat, place.lon])
        L.circleMarker([place.lat, place.lon], {
          radius: 6, color: '#fff', weight: 1.5, fillColor: COLOURS[group], fillOpacity: 1,
        }).bindTooltip(NAMES[group] + ': ' + place.name + ' (' + distance(place.km) + ')').addTo(map)
      }
    }
    L.circleMarker([centre.lat, centre.lon], {
      radius: 9, color: '#1D3631', weight: 2, fillColor: '#B8862B', fillOpacity: 1,
    }).bindTooltip(exact ? 'The flat (the spot you gave)' : centre.label).addTo(map)

    map.fitBounds(points, { padding: [24, 24], maxZoom: 16 })
    return () => map.remove()
  }, [centre, exact, places])

  return (
    <div className="map-wrap">
      <div ref={holder} className="map" role="img" aria-label="Map of the nearby places" />
      <p className="map-key">
        <span><i style={{ background: '#B8862B' }} />{exact ? 'Flat' : 'Area'}</span>
        <span><i style={{ background: COLOURS.school }} />School</span>
        <span><i style={{ background: COLOURS.hospital }} />Hospital</span>
        <span><i style={{ background: COLOURS.transit }} />Transit</span>
      </p>
    </div>
  )
}
