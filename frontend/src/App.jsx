import { useEffect, useState } from 'react'
import { api } from './api.js'
import CheckPrice from './components/CheckPrice.jsx'
import Compare from './components/Compare.jsx'
import NearbyAreas from './components/NearbyAreas.jsx'
import PlacesPage from './components/PlacesPage.jsx'
import ChecklistPage from './components/ChecklistPage.jsx'
import EmiPage from './components/EmiPage.jsx'

// each page with a small line icon for the sidebar
const PAGES = [
  { id: 'check', label: 'Check price', icon: 'M4 11l8-7 8 7v9h-5v-6H9v6H4z' },
  { id: 'compare', label: 'Compare', icon: 'M5 20V10M10 20V4M15 20v-7M20 20V8' },
  { id: 'places', label: 'Places nearby', icon: 'M12 21s-7-6.2-7-11.5a7 7 0 0114 0C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z' },
  { id: 'nearby', label: 'Other areas', icon: 'M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2zM9 4v14M15 6v14' },
  { id: 'checklist', label: 'Before you buy', icon: 'M9 11l2 2 4-4M5 4h14v16H5z' },
  { id: 'emi', label: 'Loan EMI', icon: 'M4 6h16v12H4zM4 10h16M8 15h3' },
]

// the page is kept in the address (#compare), so the back button and
// shared links open the right page
function pageFromHash() {
  const id = window.location.hash.replace('#', '')
  return PAGES.some((p) => p.id === id) ? id : 'check'
}

const START_FLAT = {
  location: 'Whitefield', size_sqft: 1200, bedrooms: 2, bathrooms: 2, asking_price: '',
  building_age: '', under_construction: false,
}

export default function App() {
  const [page, setPage] = useState(pageFromHash)
  const [areas, setAreas] = useState([])
  const [areasError, setAreasError] = useState(null)

  // what the user typed, shared by every page so they all talk about the same flat
  const [flat, setFlat] = useState(START_FLAT)
  // the flat's exact spot, if the user found it: { lat, lon, label, area }
  const [exactPoint, setExactPoint] = useState(null)
  // the last price check: { flat, result }
  const [check, setCheck] = useState(null)

  useEffect(() => {
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    api.areas().then((body) => setAreas(body.areas)).catch((error) => setAreasError(error.message))
  }, [])

  const go = (id) => {
    window.location.hash = id
    window.scrollTo({ top: 0 })
  }

  const shared = { areas, flat, setFlat, exactPoint, setExactPoint, check, setCheck, go }

  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#check" onClick={() => go('check')}>
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <path d="M4 23h24M7 23v-4M11 23v-6M15 23v-3M19 23v-7M23 23v-5M27 23v-3" />
            <path className="brand-flag" d="M19 6l3 5h-6z" />
          </svg>
          <span>
            Real Estate AVM
            <em>Flat prices in Bangalore</em>
          </span>
        </a>
        <nav aria-label="Pages">
          {PAGES.map((p) => (
            <a key={p.id} href={'#' + p.id} aria-current={page === p.id ? 'page' : undefined}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d={p.icon} /></svg>
              {p.label}
            </a>
          ))}
        </nav>
        <p className="sidebar-note">We tell you a fair price. We do not sell flats.</p>
      </aside>

      <main className="page">
        {areasError && (
          <div className="notice notice-bad" role="alert">
            {areasError}
          </div>
        )}
        {page === 'check' && <CheckPrice {...shared} />}
        {page === 'compare' && <Compare {...shared} />}
        {page === 'places' && <PlacesPage {...shared} />}
        {page === 'nearby' && <NearbyAreas {...shared} />}
        {page === 'checklist' && <ChecklistPage {...shared} />}
        {page === 'emi' && <EmiPage {...shared} />}
      </main>
    </div>
  )
}
