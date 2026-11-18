// Every call to the FastAPI backend goes through this file.
// The backend address comes from VITE_API_URL (set in .env locally, or in the
// hosting settings when deployed), and falls back to the local backend.
const BASE_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

// a free hosted backend sleeps when nobody uses it and can take up to a
// minute to wake, so requests are allowed to take that long
const TIMEOUT_MS = 75000

// ----- the login token -----
// kept in the browser so a refresh does not log you out. Browser storage can
// be switched off, so every read and write is wrapped in try/catch
const TOKEN_KEY = 'avm-login'

export function savedLogin() {
  try {
    const saved = JSON.parse(localStorage.getItem(TOKEN_KEY) || 'null')
    // the token's middle part says when it expires; drop it if it has
    const payload = JSON.parse(atob(saved.token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return payload.exp * 1000 > Date.now() ? saved : null
  } catch {
    return null
  }
}

function saveLogin(login) {
  try {
    if (login) localStorage.setItem(TOKEN_KEY, JSON.stringify(login))
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage blocked: the login lasts until the page is closed
  }
}

let currentToken = savedLogin()?.token || null
let onLoggedOut = () => {}

// App gives a function to call when the server says the login has expired
export function whenLoggedOut(callback) {
  onLoggedOut = callback
}

export function logOut() {
  currentToken = null
  saveLogin(null)
}

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
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(currentToken ? { Authorization: 'Bearer ' + currentToken } : {}),
      },
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
  if (response.status === 401 && !path.startsWith('/auth/')) {
    logOut()
    onLoggedOut()
  }
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

async function logIn(path, data) {
  const body = await post(path, data)
  currentToken = body.token
  saveLogin({ token: body.token, user: body.user })
  return body.user
}

export const api = {
  signUp: (name, email, password) => logIn('/auth/signup', { name, email, password }),
  logIn: (email, password) => logIn('/auth/login', { email, password }),
  me: () => request('/auth/me'),
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
