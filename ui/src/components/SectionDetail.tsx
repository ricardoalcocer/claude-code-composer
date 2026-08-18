import type { Section, Spec } from '../types'
import { sectionBeats } from '../types'

interface Props {
  spec: Spec
  section: Section | undefined
  sectionName: string | null
  /** Position within this section, in beats — drives the chord highlight. */
  localBeat: number | null
}

export function SectionDetail({ spec, section, sectionName, localBeat }: Props) {
  const beatsPerBar = spec.time_sig?.[0] ?? 4

  if (!section) {
    return (
      <div className="detail">
        <div className="panel-head"><h2>Section</h2></div>
        <p className="empty">
          {sectionName
            ? `The form references "${sectionName}", but no section by that name is defined.`
            : 'Pick a block on the timeline.'}
        </p>
      </div>
    )
  }

  // Chord onsets in beats, so the current chord can be highlighted while playing.
  let cursor = 0
  const chords = section.chords.map((c) => {
    const entry = { ...c, start: cursor }
    cursor += c.beats
    return entry
  })
  const activeIndex = localBeat == null ? -1
    : chords.findIndex((c) => localBeat >= c.start && localBeat < c.start + c.beats)

  return (
    <div className="detail">
      <div className="panel-head">
        <h2>{section.name}</h2>
        <span className="detail-len">
          {Math.round(sectionBeats(section) / beatsPerBar)} bars
        </span>
      </div>

      <div className="tag-row">
        {section.feel && <span className="tag">feel · {section.feel}</span>}
        {section.drums && <span className="tag">drums · {section.drums}</span>}
        {section.voicing && <span className="tag">voicing · {section.voicing}</span>}
        {section.chugg && <span className="tag">chugg · {section.chugg}</span>}
        {section.melody && <span className="tag tag-accent">composed melody</span>}
      </div>

      <div className="chord-grid">
        {chords.map((c, i) => (
          <div
            key={`${c.name}-${i}`}
            className={`chord${i === activeIndex ? ' is-active' : ''}`}
            style={{ gridColumn: `span ${Math.max(1, Math.round(c.beats / beatsPerBar))}` }}
          >
            <span className="chord-name">{c.name}</span>
            <span className="chord-beats">{c.beats}</span>
          </div>
        ))}
      </div>

      {section.scales && (
        // The improv line is the one thing you read while holding a guitar, so
        // it gets the most legible treatment on the page.
        <div className="improv">
          <span className="improv-label">improv</span>
          <p>{section.scales}</p>
        </div>
      )}

      {section.move && (
        <div className="move">
          <span className="move-label">move</span>
          <p>{section.move}</p>
        </div>
      )}

      {section.skip_roles && section.skip_roles.length > 0 && (
        <p className="skip-note">
          Layers out for this section: {section.skip_roles.join(', ')}
        </p>
      )}
    </div>
  )
}
