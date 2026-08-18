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
  /** The timeline block currently selected — target for "insert after". */
  insertAfter: { index: number; name: string; nextName: string | null } | null
  help: boolean
}

/**
 * The variant strip under the transport. Layout encodes the cost model:
 * instant deterministic ops on the left, the one model-priced ask on the
 * right. Every action creates a SIBLING folder — the original is never
 * touched, so variants are free to bin.
 */
export function TransformBar({
  spec, busy, onTransform, onPatch, onPromote, onDiscard, hasRpp, patchBusy,
  insertAfter, help,
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

  function submitInsert() {
    const desc = ask.trim()
    if (!desc || !insertAfter) return
    // The primed session already holds the full spec; naming the positions
    // and neighbours is enough context for a section that connects them.
    const after = `form position ${insertAfter.index} (${insertAfter.name})`
    const before = insertAfter.nextName
      ? `position ${insertAfter.index + 1} (${insertAfter.nextName})`
      : 'the end of the form'
    onPatch(
      `Compose a NEW section to insert between ${after} and ${before}: ${desc}. ` +
      `It must connect out of ${insertAfter.name}'s last chord and lead into ` +
      `${insertAfter.nextName ?? 'the ending'} smoothly. Give it a name not already ` +
      `used, with move and scales fields. ` +
      `Return the insert_after_index shape with insert_after_index: ${insertAfter.index}.`)
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
          <span className="vgroup-label vgroup-label-model" title="Scoped model edit — the agent changes only what you name">patch</span>
          <input
            className="patch-input"
            placeholder='e.g. "darker bridge, Phrygian colour" — changes only what you name'
            value={ask}
            onChange={(e) => setAsk(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') submitPatch() }}
            disabled={patchBusy}
          />
          <button className="vbtn vbtn-model" onClick={submitPatch} disabled={patchBusy || !ask.trim()}
                  title="Edit the named section(s) — result lands as a new sibling sketch">
            {patchBusy ? 'patching…' : 'go'}
          </button>
          <button
            className="vbtn vbtn-model"
            onClick={submitInsert}
            disabled={patchBusy || !ask.trim() || !insertAfter}
            title={insertAfter
              ? `Compose a new section that fits between ${insertAfter.name} and ${insertAfter.nextName ?? 'the end'}, described by the text on the left`
              : 'Select a block on the timeline first'}
          >
            {insertAfter ? `+ insert after ${insertAfter.name}` : '+ insert'}
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

      {help && (
        <div className="help-block">
          <p><b>instant</b> — pure math on the spec, no AI, ~100ms. Transpose to find the key
            that sits under your hands; <b>thin</b> strips to bass + one layer + drums (does the
            writing survive naked?); <b>to 7/8</b> re-bars the same harmony.</p>
          <p><b>patch</b> — a sentence to the agent, which changes <em>only</em> what you name
            (~15–90s depending on the model). Type a description, then <b>go</b> edits the section
            you describe; <b>+ insert</b> composes a brand-new section that fits between the
            selected timeline block and the next one.</p>
          <p><b>✕ bin / → REAPER</b> — the verdict. Bin moves the sketch to .bin (recoverable)
            and loads the next; REAPER renders the project from your template and opens it.</p>
        </div>
      )}
    </section>
  )
}
