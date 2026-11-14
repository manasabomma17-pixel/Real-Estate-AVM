import { useId, useMemo, useRef, useState } from 'react'

// A searchable list of the 881 areas. Typing filters the list; arrow keys
// and Enter pick an area, so it works without a mouse too.
export default function AreaPicker({ areas, value, onChange, id }) {
  const [query, setQuery] = useState(null) // null = not typing, show the chosen area
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const listId = useId()
  const listRef = useRef(null)

  const matches = useMemo(() => {
    const q = (query ?? '').trim().toLowerCase()
    if (!q) return areas.slice(0, 60)
    const starts = areas.filter((a) => a.name.toLowerCase().startsWith(q))
    const contains = areas.filter((a) => !a.name.toLowerCase().startsWith(q) && a.name.toLowerCase().includes(q))
    return [...starts, ...contains].slice(0, 60)
  }, [areas, query])

  const choose = (area) => {
    onChange(area.name)
    setQuery(null)
    setOpen(false)
  }

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, matches.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' && open && matches[active]) {
      event.preventDefault()
      choose(matches[active])
    } else if (event.key === 'Escape') {
      setQuery(null)
      setOpen(false)
    }
  }

  return (
    <div className="picker">
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && matches[active] ? listId + '-' + active : undefined}
        value={query ?? value}
        placeholder="Type an area, e.g. Hebbal"
        onFocus={(event) => {
          event.target.select()
          setOpen(true)
        }}
        onChange={(event) => {
          setQuery(event.target.value)
          setActive(0)
          setOpen(true)
        }}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => {
          setOpen(false)
          setQuery(null)
        }, 120)}
      />
      {open && (
        <ul className="picker-list" id={listId} role="listbox" ref={listRef}>
          {matches.length === 0 && <li className="picker-empty">Not found. Try a nearby area.</li>}
          {matches.map((area, i) => (
            <li
              key={area.name}
              id={listId + '-' + i}
              role="option"
              aria-selected={area.name === value}
              className={i === active ? 'is-active' : undefined}
              onMouseDown={(event) => {
                event.preventDefault()
                choose(area)
              }}
              onMouseEnter={() => setActive(i)}
            >
              <span>{area.name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
