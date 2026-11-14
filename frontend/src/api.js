// Every call to the FastAPI backend goes through this file.
// The backend address comes from VITE_API_URL (set in .env locally, or in the
// hosting settings when deployed), and falls back to the local backend.
const BASE_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

// a free hosted backend sleeps when nobody uses it and can take up to a
// minute to wake, so requests are allowed to take that long
const TIMEOUT_MS = 75000

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let response
  try {
    response = await fetch(BASE_URL + path, {
      ...options,
      signal: controller.signal,
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(
      'Cannot connect. Please try again in a minute.',
      0,
    )
  } finally {
    clearTimeout(timer)
  }

  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    // FastAPI sends a list of problems for invalid input (422), a sentence otherwise
    let detail = body.detail
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg.replace(/^Value error, /, '')).join('. ')
    throw new ApiError(detail || 'Something went wrong. Please try again.', response.status)
  }
  return body
}

const post = (path, data) => request(path, { method: 'POST', body: JSON.stringify(data) })
const area = (name) => '/areas/' + encodeURIComponent(name)

export const api = {
  areas: () => request('/areas'),
  summary: (name, bedrooms) => request(area(name) + '/summary?bedrooms=' + bedrooms),
  places: (name, point) =>
    request(area(name) + '/places' + (point ? '?lat=' + point.lat + '&lon=' + point.lon : '')),
  comparison: (name, bedrooms) => request(area(name) + '/comparison?bedrooms=' + bedrooms),
  nearbyAreas: (name) => request(area(name) + '/nearby'),
  parseListing: (text) => post('/parse-listing', { text }),
  locate: (query, areaName) => post('/locate', { query, area: areaName }),
  predict: (flat) => post('/predict', flat),
  advice: (flat, point) => post('/advice', { ...flat, exact_lat: point?.lat, exact_lon: point?.lon }),
}
