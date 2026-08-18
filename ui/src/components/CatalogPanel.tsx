import { useState } from 'react'
import type { Catalog } from '../types'

interface Props {
  catalog: Catalog | null
}

const ORDER = ['style_packs', 'song_forms', 'archetypes', 'moves']
const LABELS: Record<string, string> = {
  style_packs: 'Style packs',
  song_forms: 'Song forms',
  archetypes: 'Arrangement archetypes',
  moves: 'Moves',
}

/**
 * A read-only index of the vocabulary in SKILL.md.
 *
 * You can't pick from it — picking happens in the conversation. It's here so the
 * names are in front of you while you listen, because the depth of this project
 * is in combinations you have to know exist in order to ask for.
 */
export function CatalogPanel({ catalog }: Props) {
  const [openKey, setOpenKey] = useState<string | null>(null)

  if (!catalog) return null
  const present = ORDER.filter((k) => catalog[k]?.entries?.length)
  if (present.length === 0) return null

  return (
    <section className="catalog">
      <div className="panel-head">
        <h2>Vocabulary</h2>
        <span className="catalog-hint">name these in your next brief</span>
      </div>

      <div className="catalog-groups">
        {present.map((key) => {
          const group = catalog[key]
          const isOpen = openKey === key
          return (
            <div key={key} className={`catalog-group${isOpen ? ' is-open' : ''}`}>
              <button className="catalog-toggle" onClick={() => setOpenKey(isOpen ? null : key)}>
                <span>{LABELS[key] ?? group.title}</span>
                <span className="catalog-count">{group.entries.length}</span>
              </button>
              {isOpen && (
                <ul className="catalog-entries">
                  {group.entries.map((e) => <li key={e}>{e}</li>)}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
