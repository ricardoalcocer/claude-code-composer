import { useMemo, useState } from 'react'
import type { LibraryEntry } from '../types'

interface Props {
  songs: LibraryEntry[]
  selected: string | null
  onSelect: (rel: string) => void
  onRefresh: () => void
  loading: boolean
  root: string
}

/** Groups songs by their parent folder, preserving the newest-first ordering. */
function groupSongs(songs: LibraryEntry[]) {
  const groups = new Map<string, LibraryEntry[]>()
  for (const s of songs) {
    const key = s.group || '(root)'
    const bucket = groups.get(key)
    if (bucket) bucket.push(s)
    else groups.set(key, [s])
  }
  return [...groups.entries()]
}

export function Library({ songs, selected, onSelect, onRefresh, loading, root }: Props) {
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return songs
    return songs.filter((s) =>
      [s.dir_name, s.song_name, s.key, s.group, String(s.bpm)]
        .filter(Boolean)
        .some((f) => String(f).toLowerCase().includes(q)))
  }, [songs, query])

  const groups = useMemo(() => groupSongs(filtered), [filtered])

  return (
    <aside className="library">
      <div className="library-head">
        <div className="library-title">
          <span>Archive</span>
          <button className="ghost-btn" onClick={onRefresh} disabled={loading} title="Rescan the archive">
            {loading ? '…' : '↻'}
          </button>
        </div>
        <input
          className="search"
          placeholder="filter by key, bpm, name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="library-root" title={root}>{root}</div>
      </div>

      <div className="library-list">
        {filtered.length === 0 && (
          <p className="empty">
            {songs.length === 0
              ? 'No songs found yet. Ask Claude Code for a sketch, then hit ↻.'
              : 'Nothing matches that filter.'}
          </p>
        )}

        {groups.map(([group, entries]) => (
          <section key={group} className="library-group">
            <h3 className="group-label">{group}</h3>
            {entries.map((s) => (
              <button
                key={s.rel}
                className={`song-row${selected === s.rel ? ' is-selected' : ''}`}
                onClick={() => onSelect(s.rel)}
              >
                <span className="song-name">{s.song_name || s.slug}</span>
                <span className="song-meta">
                  {s.key && <span className="chip chip-key">{s.key}</span>}
                  {s.bpm != null && <span className="chip">{s.bpm}</span>}
                  <span className="chip chip-dim">{s.form_length} sec</span>
                  {s.has_rpp && <span className="chip chip-rpp" title="REAPER project present">RPP</span>}
                </span>
              </button>
            ))}
          </section>
        ))}
      </div>
    </aside>
  )
}
