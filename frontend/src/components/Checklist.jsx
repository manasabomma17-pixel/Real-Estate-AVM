import { useState } from 'react'

// What to check before paying anything. A price tool cannot tell whether a
// listing, seller or flat is genuine, so the buyer has to.
const STEPS = [
  { title: 'Visit the flat', text: 'Go twice, at different times of day.' },
  { title: 'Check the RERA number', text: 'For new projects. Check it on the Karnataka RERA website.' },
  { title: 'Ask for the papers', text: 'Sale deed and encumbrance certificate (EC).' },
  { title: 'Check the seller', text: 'Their ID must match the owner’s name on the papers.' },
  { title: 'Get a written agreement', text: 'Before you pay anything. Pay by bank, never cash.' },
  { title: 'Show the papers to a lawyer', text: 'Before you sign.' },
]

export default function Checklist({ verdict }) {
  const [done, setDone] = useState(() => new Set())
  const toggle = (i) => setDone((old) => {
    const next = new Set(old)
    next.has(i) ? next.delete(i) : next.add(i)
    return next
  })

  return (
    <section className="panel panel-narrow">
      {verdict === 'Looks underpriced' && (
        <div className="notice notice-warn">Your flat’s price was low. Find out why first.</div>
      )}
      <ul className="checklist">
        {STEPS.map((step, i) => (
          <li key={step.title}>
            <label className={done.has(i) ? 'is-done' : undefined}>
              <input type="checkbox" checked={done.has(i)} onChange={() => toggle(i)} />
              <span>
                <strong>{step.title}</strong>
                {step.text}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <p className="hint">{done.size} of {STEPS.length} done</p>
    </section>
  )
}
