import AreaPicker from './AreaPicker.jsx'
import ExactLocation from './ExactLocation.jsx'
import NearbyPlaces from './NearbyPlaces.jsx'

// The nearest schools, hospitals and transit stops, from the area's centre
// or from the flat's exact spot.
export default function PlacesPage({ areas, flat, setFlat, exactPoint, setExactPoint }) {
  return (
    <>
      <section className="intro">
        <h1>Places nearby</h1>
        <p className="lede">Schools, hospitals and bus or metro stops near the flat.</p>
      </section>

      <div className="sheet places-form">
        <div className="field">
          <label htmlFor="area-Places">Area</label>
          <AreaPicker id="area-Places" areas={areas} value={flat.location} onChange={(name) => setFlat((o) => ({ ...o, location: name }))} />
        </div>
        <ExactLocation flat={flat} exactPoint={exactPoint} setExactPoint={setExactPoint} />
      </div>

      <NearbyPlaces area={flat.location} exactPoint={exactPoint?.area === flat.location ? exactPoint : null} />
    </>
  )
}
