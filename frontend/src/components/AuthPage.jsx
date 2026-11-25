import { useState } from 'react'
import { api } from '../api.js'

// The first screen: log in, create an account, or reset a forgotten password.
// Modes: 'login', 'signup', 'verify' (enter the code that confirms a new
// account's email), 'forgot' (ask for the email) and 'reset' (enter the emailed
// code and a new password). Short words, one form at a time.
const HEADINGS = {
  login: ['Welcome back', 'Check if a flat’s price in Bangalore is fair.'],
  signup: ['Create your account', 'Check if a flat’s price in Bangalore is fair.'],
  forgot: ['Reset your password', 'We will email you a 6-digit code.'],
  reset: ['Enter the code', 'Check your email. The code works for 15 minutes.'],
  verify: ['Confirm your email', 'Enter the 6-digit code we emailed you.'],
}

export default function AuthPage({ onLoggedIn }) {
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const signingUp = mode === 'signup'
  const resetting = mode === 'forgot' || mode === 'reset' || mode === 'verify'
  const newPassword = signingUp || mode === 'reset'

  const switchTo = (next) => {
    setMode(next)
    setError(null)
    setInfo(null)
    if (next === 'reset' || next === 'forgot') setPassword('')
  }

  async function sendCode() {
    await api.forgotPassword(email)
    setCode('')
    switchTo('reset')
    setInfo('If this email has an account, we sent a code to ' + email.trim() + '.')
  }

  async function submit(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'forgot') {
        await sendCode()
        setBusy(false)
        return
      }
      const user =
        mode === 'signup' ? await api.signUp(name, email, password)
        : mode === 'reset' ? await api.resetPassword(email, code, password)
        : mode === 'verify' ? await api.verifyEmail(email, code)
        : await api.logIn(email, password)
      if (user?.needs_verification) {
        setCode('')
        switchTo('verify')
        setInfo('We sent a 6-digit code to ' + user.email + '.')
        setBusy(false)
        return
      }
      onLoggedIn(user)
    } catch (err) {
      // an account that has not confirmed its email yet
      if (err.status === 403 && mode === 'login') {
        setCode('')
        switchTo('verify')
        setInfo('Please confirm your email first. Enter the code we sent, or send a new one.')
      } else {
        setError(err.message)
      }
      setBusy(false)
    }
  }

  async function sendAgain() {
    setError(null)
    setBusy(true)
    try {
      if (mode === 'verify') {
        await api.resendCode(email)
        setInfo('If this email is waiting for a code, we sent a new one.')
      } else {
        await sendCode()
      }
    } catch (err) {
      setError(err.message)
    }
    setBusy(false)
  }

  const wrongLogin = mode === 'login' && error
    && (error.startsWith('Wrong email or password') || error.startsWith('Too many wrong tries'))
  const [heading, lede] = HEADINGS[mode]
  const buttonText = { login: 'Log in', signup: 'Create account', forgot: 'Send code', reset: 'Save new password',
    verify: 'Confirm email' }[mode]

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
        <h1>{heading}</h1>
        <p className="lede">{lede}</p>

        {!resetting && (
          <div className="auth-switch" role="group" aria-label="Log in or create an account">
            <button type="button" aria-pressed={!signingUp} onClick={() => switchTo('login')}>Log in</button>
            <button type="button" aria-pressed={signingUp} onClick={() => switchTo('signup')}>Create account</button>
          </div>
        )}

        <form className="auth-form" onSubmit={submit}>
          {signingUp && (
            <div className="field">
              <label htmlFor="auth-name">Your name</label>
              <input id="auth-name" value={name} autoComplete="name" required
                onChange={(e) => setName(e.target.value)} />
            </div>
          )}

          {mode !== 'reset' && mode !== 'verify' && (
            <div className="field">
              <label htmlFor="auth-email">Email</label>
              <input id="auth-email" type="email" value={email} autoComplete="email" required
                placeholder="you@example.com" onChange={(e) => setEmail(e.target.value)} />
            </div>
          )}

          {info && <div className="notice notice-good" role="status">{info}</div>}

          {(mode === 'reset' || mode === 'verify') && (
            <div className="field">
              <label htmlFor="auth-code">6-digit code</label>
              <input id="auth-code" className="code-input" value={code} required inputMode="numeric"
                autoComplete="one-time-code" maxLength={7} pattern="[0-9 ]{6,7}" placeholder="123456"
                onChange={(e) => setCode(e.target.value.replace(/[^0-9 ]/g, ''))} />
            </div>
          )}

          {mode !== 'forgot' && mode !== 'verify' && (
            <div className="field">
              <div className="label-row">
                <label htmlFor="auth-password">{mode === 'reset' ? 'New password' : 'Password'}</label>
                {mode === 'login' && (
                  <button type="button" className="link-button small" onClick={() => switchTo('forgot')}>
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="input-unit">
                <input id="auth-password" type={showPassword ? 'text' : 'password'} value={password} required
                  minLength={newPassword ? 8 : undefined}
                  autoComplete={newPassword ? 'new-password' : 'current-password'}
                  onChange={(e) => setPassword(e.target.value)} />
                <button type="button" className="show-password" onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {newPassword && <p className="hint">At least 8 characters.</p>}
            </div>
          )}

          {error && (
            <div className="notice notice-bad" role="alert">
              {error}
              {wrongLogin && (
                <>
                  {' '}
                  <button type="button" className="link-button" onClick={() => switchTo('forgot')}>
                    Reset your password
                  </button>
                </>
              )}
            </div>
          )}

          <button className="button button-primary button-wide" type="submit" disabled={busy}>
            {busy ? 'Please wait…' : buttonText}
          </button>
          {busy && <p className="hint" role="status">The first time can take up to 1 minute while the server starts.</p>}
        </form>

        {(mode === 'reset' || mode === 'verify') && (
          <p className="auth-foot">
            No email? Check spam, or{' '}
            <button type="button" className="link-button" disabled={busy} onClick={sendAgain}>send a new code</button>
          </p>
        )}

        <p className="auth-foot">
          {resetting ? 'Remember it? ' : signingUp ? 'Already have an account? ' : 'New here? '}
          <button type="button" className="link-button" onClick={() => switchTo(resetting || signingUp ? 'login' : 'signup')}>
            {resetting || signingUp ? 'Log in' : 'Create an account'}
          </button>
        </p>
      </div>
    </div>
  )
}
