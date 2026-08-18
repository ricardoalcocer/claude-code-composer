import { useCallback, useMemo, useRef } from 'react'
import type { Spec } from '../types'
import { formTimeline, sectionHues } from '../types'

interface Props {
  spec: Spec
  position: number
  selectedIndex: number | null
  loop: { start: number; end: number } | null
  onSelect: (index: number) => void
  onSeek: (beat: number) => void
}

export function FormTimeline({ spec, position, selectedIndex, loop, onSelect, onSeek }: Props) {
  const railRef = useRef<HTMLDivElement>(null)
  const positions = useMemo(() => formTimeline(spec), [spec])
  const hues = useMemo(() => sectionHues(spec), [spec])
  const total = positions.reduce((n, p) => n + p.beats, 0) || 1
  const beatsPerBar = spec.time_sig?.[0] ?? 4

  const seekFromEvent = useCallback((clientX: number) => {
    const rail = railRef.current
    if (!rail) return
    const rect = rail.getBoundingClientRect()
    const ratio = Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1)
    onSeek(ratio * total)
  }, [onSeek, total])

  return (
    <div className="timeline">
      <div className="timeline-scale">
        <span>bar 1</span>
        <span>{Math.round(total / beatsPerBar)} bars · {total} beats</span>
      </div>

      <div
        className="timeline-rail"
        ref={railRef}
        onClick={(e) => seekFromEvent(e.clientX)}
        role="slider"
        tabIndex={0}
        aria-label="Song position"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={Math.round(position)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') { e.preventDefault(); onSeek(Math.min(position + beatsPerBar, total)) }
          if (e.key === 'ArrowLeft') { e.preventDefault(); onSeek(Math.max(position - beatsPerBar, 0)) }
        }}
      >
        {loop && (
          <div
            className="timeline-loop"
            style={{
              left: `${(loop.start / total) * 100}%`,
              width: `${((loop.end - loop.start) / total) * 100}%`,
            }}
          />
        )}

        {positions.map((p) => {
          const hue = hues.get(p.name) ?? 20
          const isActive = position >= p.startBeat && position < p.startBeat + p.beats
          const isSelected = selectedIndex === p.index
          return (
            <button
              key={p.index}
              className={`form-block${isSelected ? ' is-selected' : ''}${isActive ? ' is-active' : ''}`}
              style={{
                width: `${(p.beats / total) * 100}%`,
                // Blocks are tinted, not saturated — the playhead and the
                // selection ring need to stay the loudest things on the rail.
                background: `hsl(${hue} 46% ${isActive ? 32 : 22}%)`,
                borderColor: `hsl(${hue} 52% ${isActive ? 58 : 38}%)`,
              }}
              onClick={(e) => { e.stopPropagation(); onSelect(p.index); onSeek(p.startBeat) }}
              title={`${p.name} — ${Math.round(p.beats / beatsPerBar)} bars${p.section?.feel ? ` · ${p.section.feel}` : ''}`}
            >
              <span className="form-block-name">{p.name}</span>
              <span className="form-block-bars">{Math.round(p.beats / beatsPerBar)}</span>
            </button>
          )
        })}

        <div className="playhead" style={{ left: `${(position / total) * 100}%` }} />
      </div>
    </div>
  )
}
