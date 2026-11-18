import { useState } from 'react'
import { api } from '../api.js'

// The first screen: log in, or create an account. Short words, one form.
export default function AuthPage({ onLoggedIn }) {
  const [mode, setMode] = useState('login') // 'login' or 'signup'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const signingUp = mode === 'signup'

  async function submit(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const user = signingUp ? await api.signUp(name, email, password) : await api.logIn(email, password)
      onLoggedIn(user)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const switchTo = (next) => {
    setMode(next)
    setError(null)
  }

  return (
    <div className="auth">
      <div className="auth-card">
        <div className="auth-brand">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <path d="M4 23h24M7 23v-4M11 23v-6M15 23v-3M19 23v-7M23 23v-5M27 23v-3" />
            <path className="brand-flag" d="M19 6l3 5h-6z" />
          </svg>
          <span>Real Estate AVM</span>
        </div>
        <h1>{signingUp ? 'Create your account' : 'Welcome back'}</h1>
        <p className="lede">Check if a flat’s price in Bangalore is fair.</p>

        <div className="auth-switch" role="group" aria-label="Log in or create an account">
          <button type="button" aria-pressed={!signingUp} onClick={() => switchTo('login')}>Log in</button>
          <button type="button" aria-pressed={signingUp} onClick={() => switchTo('signup')}>Create account</button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {signingUp && (
            <div className="field">
              <label htmlFor="auth-name">Your name</label>
              <input id="auth-name" value={name} autoComplete="name" required
                onChange={(e) => setName(e.target.value)} />
            </div>
          )}
          <div className="field">
            <label htmlFor="auth-email">Email</label>
            <input id="auth-email" type="email" value={email} autoComplete="email" required
              placeholder="you@example.com" onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="auth-password">Password</label>
            <div className="input-unit">
              <input id="auth-password" type={showPassword ? 'text' : 'password'} value={password} required
                minLength={signingUp ? 8 : undefined}
                autoComplete={signingUp ? 'new-password' : 'current-password'}
                onChange={(e) => setPassword(e.target.value)} />
              <button type="button" className="show-password" onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
            {signingUp && <p className="hint">At least 8 characters.</p>}
          </div>

          {error && <div className="notice notice-bad" role="alert">{error}</div>}

          <button className="button button-primary button-wide" type="submit" disabled={busy}>
            {busy ? 'Please wait…' : signingUp ? 'Create account' : 'Log in'}
          </button>
          {busy && <p className="hint" role="status">The first time can take up to 1 minute while the server starts.</p>}
        </form>

        <p className="auth-foot">
          {signingUp ? 'Already have an account? ' : 'New here? '}
          <button type="button" className="link-button" onClick={() => switchTo(signingUp ? 'login' : 'signup')}>
            {signingUp ? 'Log in' : 'Create an account'}
          </button>
        </p>
      </div>
    </div>
  )
}
