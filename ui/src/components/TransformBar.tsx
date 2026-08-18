import { useState } from 'react'
import type { Role, Spec } from '../types'
import { specRoles } from '../types'

interface Props {
  spec: Spec
  busy: boolean
  /** Tier 0 — deterministic; lands in ~60ms as a sibling variant. */
  onTransform: (op: string, arg?: unknown) => void
  /** Tier 1 — scoped model patch; ~15–30s through the warm session. */
  onPatch: (ask: string) => void
  /** Renders the .RPP and opens it in REAPER — the keeper path. */
  onPromote: () => void
  /** Moves the sketch to .bin and advances to the next one — the "didn't inspire" path. */
  onDiscard: () => void
  hasRpp: boolean
  patchBusy: boolean
}

/**
 * The variant strip under the transport. Layout encodes the cost model:
 * instant deterministic ops on the left, the one model-priced ask on the
 * right. Every action creates a SIBLING folder — the original is never
 * touched, so variants are free to bin.
 */
export function TransformBar({
  spec, busy, onTransform, onPatch, onPromote, onDiscard, hasRpp, patchBusy,
}: Props) {
  const [ask, setAsk] = useState('')
  const roles = specRoles(spec)
  const inSeven = spec.time_sig?.[0] === 7 && spec.time_sig?.[1] === 8

  const t = (op: string, arg?: unknown) => () => onTransform(op, arg)

  function submitPatch() {
    const text = ask.trim()
    if (!text) return
    onPatch(text)
    setAsk('')
  }

  return (
    <section className="variantbar">
      <div className="variant-groups">
        <div className="vgroup">
          <span className="vgroup-label" title="Deterministic — no model, ~60ms">instant</span>
          <button className="vbtn" onClick={t('transpose', 2)} disabled={busy} title="Transpose up a whole step">+2</button>
          <button className="vbtn" onClick={t('transpose', -2)} disabled={busy} title="Transpose down a whole step">−2</button>
          <button className="vbtn" onClick={t('transpose', 5)} disabled={busy} title="Transpose up a fourth">+5</button>
          <span className="vsep" />
          <button className="vbtn" onClick={t('tempo', Math.round(spec.tempo * 0.85))} disabled={busy}
                  title={`Slower — ${Math.round(spec.tempo * 0.85)} BPM`}>slower</button>
          <button className="vbtn" onClick={t('tempo', Math.round(spec.tempo * 1.15))} disabled={busy}
                  title={`Faster — ${Math.round(spec.tempo * 1.15)} BPM`}>faster</button>
          <span className="vsep" />
          <button className="vbtn" onClick={t('rebar', inSeven ? '4/4' : '7/8')} disabled={busy}
                  title="Re-bar, preserving bar counts">{inSeven ? 'to 4/4' : 'to 7/8'}</button>
          <button className="vbtn" onClick={t('thin')} disabled={busy}
                  title="Bass + one harmony layer + drums — does the writing survive stripped down?">thin</button>
          {roles.includes('drums') && (
            <button className="vbtn" onClick={t('drop_role', 'drums' satisfies Role)} disabled={busy}
                    title="Variant without drums">no drums</button>
          )}
        </div>

        <div className="vgroup vgroup-patch">
          <span className="vgroup-label vgroup-label-model" title="Scoped model patch — ~15–30s">patch</span>
          <input
            className="patch-input"
            placeholder='e.g. "darker bridge, Phrygian colour" — returns only the changed section'
            value={ask}
            onChange={(e) => setAsk(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') submitPatch() }}
            disabled={patchBusy}
          />
          <button className="vbtn vbtn-model" onClick={submitPatch} disabled={patchBusy || !ask.trim()}>
            {patchBusy ? 'patching…' : 'go'}
          </button>
        </div>

        <div className="vgroup vgroup-promote">
          <button
            className="bin-btn"
            onClick={onDiscard}
            disabled={busy}
            title="Move this sketch to .bin (recoverable) and load the next one"
          >
            ✕ bin
          </button>
          <button
            className={`promote-btn${hasRpp ? ' is-done' : ''}`}
            onClick={onPromote}
            disabled={busy || hasRpp}
            title={hasRpp ? 'REAPER project already rendered'
              : 'Render the .RPP and open it in REAPER'}
          >
            {hasRpp ? '✓ in REAPER' : '→ take to REAPER'}
          </button>
        </div>
      </div>
      <p className="variant-note">
        every action writes a <em>sibling</em> variant — the original is never touched
      </p>
    </section>
  )
}
