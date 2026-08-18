import { useEffect, useState } from 'react'
import type { ComposeResult, Spec } from '../types'

interface Props {
  spec: Spec
  rel: string
  busy: boolean
  result: ComposeResult | null
  onRegenerate: (spec: Spec, midiOnly: boolean) => void
}

/**
 * A raw JSON editor, on purpose.
 *
 * A form with dropdowns for feel/voicing/archetype would be the obvious thing to
 * build here, and it would be the wrong thing: it would quietly become a worse
 * interface for the decisions SKILL.md hands to Claude. This is for the small
 * edit you already know you want — nudge the tempo, swap one chord, reorder the
 * form — then hear it. Anything bigger is a sentence to Claude, not a form.
 */
export function SpecEditor({ spec, rel, busy, result, onRegenerate }: Props) {
  const [text, setText] = useState(() => JSON.stringify(spec, null, 2))
  const [error, setError] = useState<string | null>(null)
  const [midiOnly, setMidiOnly] = useState(false)
  const [open, setOpen] = useState(false)

  // Reload the buffer whenever a different song (or a regenerated one) arrives.
  useEffect(() => {
    setText(JSON.stringify(spec, null, 2))
    setError(null)
  }, [spec, rel])

  const dirty = text !== JSON.stringify(spec, null, 2)

  function submit() {
    let parsed: Spec
    try {
      parsed = JSON.parse(text)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'invalid JSON')
      return
    }
    setError(null)
    onRegenerate(parsed, midiOnly)
  }

  return (
    <section className={`editor${open ? ' is-open' : ''}`}>
      <button className="editor-toggle" onClick={() => setOpen((v) => !v)}>
        <span>{open ? '▾' : '▸'} spec.json</span>
        {dirty && <span className="dirty-dot" title="unsaved edits">●</span>}
        <span className="editor-path">{rel}</span>
      </button>

      {open && (
        <div className="editor-body">
          <textarea
            spellCheck={false}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={20}
          />

          {error && <p className="editor-error">JSON error — {error}</p>}

          <div className="editor-actions">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={midiOnly}
                onChange={(e) => setMidiOnly(e.target.checked)}
              />
              --midi-only (skip the .RPP)
            </label>
            <button className="primary-btn" onClick={submit} disabled={busy}>
              {busy ? 'running composer.py…' : 'Regenerate & reload'}
            </button>
          </div>

          <p className="editor-warning">
            Regenerating overwrites this folder's <code>.mid</code>
            {midiOnly ? '' : ', .RPP'} and <code>spec.json</code> in place.
          </p>

          {result && (
            <pre className={`compose-log${result.ok ? '' : ' is-error'}`}>
              {result.ok
                ? result.stdout.trim() || 'done'
                : (result.stderr.trim() || `exit ${result.returncode}`)}
            </pre>
          )}
        </div>
      )}
    </section>
  )
}
