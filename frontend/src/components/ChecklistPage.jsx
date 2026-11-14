import Checklist from './Checklist.jsx'

export default function ChecklistPage({ check }) {
  return (
    <>
      <section className="intro">
        <h1>Before you buy</h1>
        <p className="lede">Do these before you pay any money.</p>
      </section>
      <Checklist verdict={check?.typo ? null : check?.result.verdict} />
    </>
  )
}
