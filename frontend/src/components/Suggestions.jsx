import { useState } from 'react'

// Short tips worked out by the backend from real numbers. The 3 most
// useful show first; the rest are one tap away.
const LABEL = { good: 'Good', warning: 'Be careful', info: 'Good to know' }
const SHOWN = 3

export default function Suggestions({ items }) {
  const [all, setAll] = useState(false)
  const shown = all ? items : items.slice(0, SHOWN)
  return (
    <section className="panel">
      <h3>Tips</h3>
      <ul className="suggestions">
        {shown.map((item) => (
          <li key={item.title} className={'suggestion suggestion-' + item.kind}>
            <span className="suggestion-mark" aria-label={LABEL[item.kind]} />
            <div>
              <h4>{item.title}</h4>
              <p>{item.text}</p>
            </div>
          </li>
        ))}
      </ul>
      {items.length > SHOWN && (
        <button type="button" className="link-button" onClick={() => setAll(!all)}>
          {all ? 'Show fewer tips' : 'Show ' + (items.length - SHOWN) + ' more tips'}
        </button>
      )}
    </section>
  )
}
