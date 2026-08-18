import { useState } from 'react'
import type { AgentJob } from '../types'

interface Props {
  jobs: AgentJob[]
  claudeAvailable: boolean
  backend: string
  busy: boolean
  onGenerate: (brief: string, count: number) => void
  onOpenResult: (rel: string) => void
}

/**
 * The brief stays a sentence — the same one you'd type to Claude Code — never
 * a form. The one knob is fan-out count: one cold brief is ~3 minutes, so the
 * rational move is asking for several takes and auditioning while they land.
 */
export function GenerateBar({ jobs, claudeAvailable, backend, busy, onGenerate, onOpenResult }: Props) {
  const [brief, setBrief] = useState('')
  const [count, setCount] = useState(2)

  const active = jobs.filter((j) => j.status === 'running' || j.status === 'queued')
  const recent = jobs.filter((j) => j.status === 'done' || j.status === 'error').slice(0, 4)

  function submit() {
    const text = brief.trim()
    if (!text) return
    onGenerate(text, count)
    setBrief('')
  }

  return (
    <section className="genbar">
      <div className="genbar-row">
        <input
          className="brief-input"
          placeholder={claudeAvailable
            ? 'brief — e.g. "modal-cinematic Zimmer build in Cm, no V chord, glacial harmonic rhythm"'
            : 'no agent CLI found (claude or opencode) — generation disabled, audition still works'}
          value={brief}
          disabled={!claudeAvailable}
          onChange={(e) => setBrief(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
        />
        <div className="count-pick" title="How many independent takes to generate">
          {[1, 2, 4].map((n) => (
            <button
              key={n}
              className={`count-btn${count === n ? ' is-on' : ''}`}
              onClick={() => setCount(n)}
              disabled={!claudeAvailable}
            >{n}</button>
          ))}
        </div>
        <button
          className="primary-btn"
          onClick={submit}
          disabled={!claudeAvailable || busy || !brief.trim()}
          title={claudeAvailable ? `generates via ${backend}` : undefined}
        >
          Generate
        </button>
        {claudeAvailable && backend && (
          <span className="backend-tag" title="Agent CLI used for generation — set agent_backend in config.json">
            via {backend}
          </span>
        )}
      </div>

      {(active.length > 0 || recent.length > 0) && (
        <div className="job-strip">
          {active.map((j) => (
            <span key={j.id} className="job job-running" title={j.label}>
              <span className="job-spin" />
              {j.kind === 'patch' ? 'patch' : j.kind === 'prime' ? 'priming' : 'take'}
              {' · '}{Math.round(j.elapsed)}s
            </span>
          ))}
          {recent.map((j) => (
            j.status === 'done' && j.rel ? (
              <button key={j.id} className="job job-done" title={j.label}
                      onClick={() => onOpenResult(j.rel!)}>
                ✓ {j.rel.split('/').pop()} · {Math.round(j.elapsed)}s
              </button>
            ) : (
              <span key={j.id} className="job job-error" title={j.detail || j.label}>
                ✕ {j.kind} failed
              </span>
            )
          ))}
        </div>
      )}
    </section>
  )
}
