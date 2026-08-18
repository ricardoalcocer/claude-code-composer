import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as api from './api'
import { parseSmf, type ParsedMidi } from './midi/parseSmf'
import { usePlayback } from './hooks/usePlayback'
import { Library } from './components/Library'
import { FormTimeline } from './components/FormTimeline'
import { Transport } from './components/Transport'
import { RoleRack } from './components/RoleRack'
import { SectionDetail } from './components/SectionDetail'
import { SpecEditor } from './components/SpecEditor'
import { CatalogPanel } from './components/CatalogPanel'
import type {
  Catalog, ComposeResult, LibraryEntry, ServerConfig, SongPayload, Spec,
} from './types'
import { formTimeline, specRoles, totalBeats } from './types'

export default function App() {
  const [config, setConfig] = useState<ServerConfig | null>(null)
  const [songs, setSongs] = useState<LibraryEntry[]>([])
  const [root, setRoot] = useState('')
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [loadingLibrary, setLoadingLibrary] = useState(true)

  const [selectedRel, setSelectedRel] = useState<string | null>(null)
  const [song, setSong] = useState<SongPayload | null>(null)
  const [midi, setMidi] = useState<ParsedMidi | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [loopOn, setLoopOn] = useState(false)

  const [busy, setBusy] = useState(false)
  const [composeResult, setComposeResult] = useState<ComposeResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const playback = usePlayback()
  const { engine, load, seek, setLoop } = playback

  // --- data loading ---

  const refreshLibrary = useCallback(async () => {
    setLoadingLibrary(true)
    try {
      const lib = await api.getLibrary()
      setSongs(lib.songs)
      setRoot(lib.root)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'could not reach the bridge server')
    } finally {
      setLoadingLibrary(false)
    }
  }, [])

  useEffect(() => {
    void refreshLibrary()
    api.getConfig().then(setConfig).catch(() => {})
    api.getCatalog().then(setCatalog).catch(() => {})
  }, [refreshLibrary])

  const loadSong = useCallback(async (rel: string) => {
    setError(null)
    setComposeResult(null)
    try {
      const payload = await api.getSong(rel)
      setSong(payload)
      setSelectedRel(rel)
      setSelectedIndex(payload.spec.form.length > 0 ? 0 : null)
      setLoopOn(false)

      if (payload.files.some((f) => f.name === 'full.mid')) {
        const buf = await api.fetchMidi(rel, 'full.mid')
        const parsed = parseSmf(buf)
        setMidi(parsed)
        // The spec is authoritative for length. full.mid runs slightly past the
        // form — a pad ringing over the last barline — and if the engine used
        // that length the playhead would overshoot the end of the timeline,
        // which is drawn from the spec. Fall back to the file only for specs
        // with no measurable form.
        const specBeats = totalBeats(payload.spec)
        load(parsed.tracks, payload.spec.tempo, specBeats > 0 ? specBeats : parsed.totalBeats)
      } else {
        setMidi(null)
        load([], payload.spec.tempo, totalBeats(payload.spec))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'could not load that song')
      setMidi(null)
    }
  }, [load])

  // Open the newest song once, so the app isn't a blank page on first run.
  const autoOpened = useRef(false)
  useEffect(() => {
    if (autoOpened.current || songs.length === 0 || selectedRel) return
    autoOpened.current = true
    void loadSong(songs[0].rel)
  }, [songs, selectedRel, loadSong])

  // --- derived ---

  const spec = song?.spec ?? null
  const positions = useMemo(() => (spec ? formTimeline(spec) : []), [spec])
  const total = useMemo(() => (spec ? totalBeats(spec) : 0), [spec])
  const roles = useMemo(() => (spec ? specRoles(spec) : []), [spec])
  const beatsPerBar = spec?.time_sig?.[0] ?? 4

  const noteCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const t of midi?.tracks ?? []) {
      const role = t.role ?? t.name
      counts[role] = (counts[role] ?? 0) + t.notes.length
    }
    return counts
  }, [midi])

  const selectedPosition = selectedIndex != null ? positions[selectedIndex] : undefined

  // While playing, the detail panel follows the playhead; when parked, it shows
  // whatever block you clicked.
  const playingPosition = useMemo(
    () => positions.find((p) => playback.position >= p.startBeat
      && playback.position < p.startBeat + p.beats),
    [positions, playback.position])

  const shownPosition = playback.playing ? (playingPosition ?? selectedPosition) : selectedPosition
  const localBeat = shownPosition && playback.playing
    ? playback.position - shownPosition.startBeat
    : null

  // --- transport wiring ---

  const toggleLoop = useCallback(() => {
    if (!selectedPosition) return
    const next = !loopOn
    setLoopOn(next)
    setLoop(next ? { start: selectedPosition.startBeat, end: selectedPosition.startBeat + selectedPosition.beats } : null)
  }, [selectedPosition, loopOn, setLoop])

  // Keep an armed loop pointed at whichever block is selected.
  useEffect(() => {
    if (!loopOn || !selectedPosition) return
    setLoop({ start: selectedPosition.startBeat, end: selectedPosition.startBeat + selectedPosition.beats })
  }, [loopOn, selectedPosition, setLoop])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null
      if (el && ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return
      if (e.code === 'Space') { e.preventDefault(); playback.toggle() }
      if (e.code === 'ArrowRight') { e.preventDefault(); seek(Math.min(playback.position + beatsPerBar, total)) }
      if (e.code === 'ArrowLeft') { e.preventDefault(); seek(Math.max(playback.position - beatsPerBar, 0)) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playback, seek, beatsPerBar, total])

  // --- regenerate ---

  const regenerate = useCallback(async (nextSpec: Spec, midiOnly: boolean) => {
    if (!selectedRel) return
    setBusy(true)
    setComposeResult(null)
    try {
      const result = await api.compose({ spec: nextSpec, rel: selectedRel, midi_only: midiOnly })
      setComposeResult(result)
      if (result.ok) {
        playback.stop()
        await loadSong(selectedRel)
        void refreshLibrary()
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'regenerate failed')
    } finally {
      setBusy(false)
    }
  }, [selectedRel, loadSong, refreshLibrary, playback])

  // --- render ---

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">▮▮▮</span>
          <span className="brand-name">claude-composer</span>
          <span className="brand-sub">sketchpad</span>
        </div>
        <div className="topbar-right">
          {config && !config.output_root_exists && (
            <span className="warn">archive root does not exist yet</span>
          )}
          {error && <span className="warn">{error}</span>}
        </div>
      </header>

      <div className="body">
        <Library
          songs={songs}
          selected={selectedRel}
          onSelect={(rel) => { playback.stop(); void loadSong(rel) }}
          onRefresh={refreshLibrary}
          loading={loadingLibrary}
          root={root || config?.output_root || ''}
        />

        <main className="main">
          {!spec && (
            <div className="placeholder">
              <h2>Nothing loaded</h2>
              <p>
                Pick a sketch from the archive, or ask Claude Code for a new one and hit ↻.
              </p>
            </div>
          )}

          {spec && (
            <>
              <section className="song-head">
                <h1>{spec.song_name ?? song?.rel}</h1>
                <div className="song-facts">
                  {spec.key && <span className="fact fact-key">{spec.key}</span>}
                  <span className="fact">{spec.tempo} BPM</span>
                  <span className="fact">{beatsPerBar}/{spec.time_sig?.[1] ?? 4}</span>
                  <span className="fact fact-dim">{spec.sections.length} sections</span>
                  <span className="fact fact-dim">{spec.form.length} in form</span>
                  {!midi && <span className="fact fact-warn">no full.mid — cannot play</span>}
                </div>
              </section>

              <FormTimeline
                spec={spec}
                position={playback.position}
                selectedIndex={selectedIndex}
                loop={engine.loop}
                onSelect={setSelectedIndex}
                onSeek={seek}
              />

              <Transport
                playing={playback.playing}
                position={playback.position}
                totalBeats={total}
                beatsPerBar={beatsPerBar}
                tempo={spec.tempo}
                loopActive={loopOn}
                canLoop={selectedPosition != null}
                loopLabel={selectedPosition ? selectedPosition.name : 'section'}
                onToggle={() => playback.toggle()}
                onStop={() => { playback.stop(); seek(0) }}
                onToggleLoop={toggleLoop}
              />

              <div className="panels">
                <RoleRack
                  roles={roles}
                  noteCounts={noteCounts}
                  section={shownPosition?.section}
                  isMuted={(r) => engine.isMuted(r)}
                  isSoloed={(r) => engine.isSoloed(r)}
                  anySolo={engine.anySolo}
                  onMute={playback.setMuted}
                  onSolo={playback.setSoloed}
                />

                <SectionDetail
                  spec={spec}
                  section={shownPosition?.section}
                  sectionName={shownPosition?.name ?? null}
                  localBeat={localBeat}
                />
              </div>

              <div className="panels panels-lower">
                <CatalogPanel catalog={catalog} />

                <div className="downloads">
                  <div className="panel-head"><h2>Files</h2></div>
                  <ul className="file-list">
                    {song?.files.map((f) => (
                      <li key={f.name}>
                        <a href={api.fileUrl(song.rel, f.name)} download={f.name}>{f.name}</a>
                        <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {selectedRel && (
                <SpecEditor
                  spec={spec}
                  rel={selectedRel}
                  busy={busy}
                  result={composeResult}
                  onRegenerate={regenerate}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
