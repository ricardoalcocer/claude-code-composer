interface Props {
  playing: boolean
  position: number
  totalBeats: number
  beatsPerBar: number
  tempo: number
  loopActive: boolean
  canLoop: boolean
  loopLabel: string
  onToggle: () => void
  onStop: () => void
  onToggleLoop: () => void
}

function barBeat(position: number, beatsPerBar: number) {
  const bar = Math.floor(position / beatsPerBar) + 1
  const beat = Math.floor(position % beatsPerBar) + 1
  return `${bar}.${beat}`
}

function clock(position: number, tempo: number) {
  const seconds = (position / tempo) * 60
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export function Transport({
  playing, position, totalBeats, beatsPerBar, tempo,
  loopActive, canLoop, loopLabel, onToggle, onStop, onToggleLoop,
}: Props) {
  return (
    <div className="transport">
      <button className={`play-btn${playing ? ' is-playing' : ''}`} onClick={onToggle}
              title={playing ? 'Pause (space)' : 'Play (space)'}>
        {playing ? '❚❚' : '▶'}
      </button>
      <button className="ghost-btn stop-btn" onClick={onStop} title="Stop and rewind">■</button>

      <div className="readout">
        <span className="readout-main">{barBeat(position, beatsPerBar)}</span>
        <span className="readout-sub">
          {clock(position, tempo)} / {clock(totalBeats, tempo)}
        </span>
      </div>

      <button
        className={`loop-btn${loopActive ? ' is-on' : ''}`}
        onClick={onToggleLoop}
        disabled={!canLoop}
        title={canLoop ? 'Loop the selected section' : 'Select a section on the timeline first'}
      >
        ⟳ {loopLabel}
      </button>

      <span className="transport-hint">space play · ←/→ scrub a bar</span>
    </div>
  )
}
