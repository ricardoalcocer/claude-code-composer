import type { MidiTrack } from '../midi/parseSmf'
import {
  DEFAULT_DRUM, FALLBACK_VOICE, TONE_VOICES, drumFor, midiToHz,
} from './voices'

/**
 * Lookahead scheduler over Web Audio.
 *
 * A 48-bar sketch is a few thousand notes; creating every node up front stalls
 * the tab and makes seeking impossible. Instead a timer wakes every SCHEDULE_MS
 * and materialises only the notes starting inside the next LOOKAHEAD_S — the
 * standard "tale of two clocks" arrangement, where setInterval decides *when to
 * think* and AudioContext.currentTime decides *when things sound*.
 */

const LOOKAHEAD_S = 0.25   // how far ahead of the audio clock we schedule
const SCHEDULE_MS = 40     // how often the scheduler wakes
const CHUNK_BEATS = 2      // max beats materialised per inner pass

/** One contiguous run of song time, used to map audio time back to a beat. */
interface Segment {
  startTime: number
  endTime: number
  startBeat: number
}

export interface EngineState {
  playing: boolean
  positionBeats: number
}

export class PlaybackEngine {
  private ctx: AudioContext | null = null
  private master: GainNode | null = null
  private roleGains = new Map<string, GainNode>()
  private noiseBuffer: AudioBuffer | null = null

  private tracks: MidiTrack[] = []
  private tempoBpm = 120

  private timer: number | null = null
  private live: AudioScheduledSourceNode[] = []
  private segments: Segment[] = []

  /** Song position and audio time of the next not-yet-scheduled beat. */
  private cursorBeat = 0
  private cursorTime = 0
  private stopAtTime: number | null = null

  private loopRange: { start: number; end: number } | null = null
  private songEndBeat = 0
  private muted = new Set<string>()
  private soloed = new Set<string>()
  private playing = false

  onStateChange: ((s: EngineState) => void) | null = null

  // --- lifecycle ---

  private ensureContext(): AudioContext {
    if (!this.ctx) {
      const Ctor: typeof AudioContext =
        window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      this.ctx = new Ctor()
      const master = this.ctx.createGain()
      master.gain.value = 0.85

      // Keeps a full-band chorus from clipping without needing a mixdown.
      const comp = this.ctx.createDynamicsCompressor()
      comp.threshold.value = -14
      comp.ratio.value = 4
      comp.attack.value = 0.004
      comp.release.value = 0.18

      master.connect(comp)
      comp.connect(this.ctx.destination)
      this.master = master

      // One shared noise buffer for every drum hit — cheap and plenty.
      const frames = Math.floor(this.ctx.sampleRate * 1.5)
      const buf = this.ctx.createBuffer(1, frames, this.ctx.sampleRate)
      const data = buf.getChannelData(0)
      for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1
      this.noiseBuffer = buf
    }
    return this.ctx
  }

  private roleGain(role: string): GainNode {
    const ctx = this.ensureContext()
    let g = this.roleGains.get(role)
    if (!g) {
      g = ctx.createGain()
      g.gain.value = 1
      g.connect(this.master!)
      this.roleGains.set(role, g)
    }
    return g
  }

  load(tracks: MidiTrack[], tempoBpm: number, songEndBeat: number) {
    this.stop()
    this.tracks = tracks
    this.tempoBpm = tempoBpm > 0 ? tempoBpm : 120
    this.songEndBeat = songEndBeat
    this.loopRange = null
    this.cursorBeat = 0
    this.emit()
  }

  dispose() {
    this.stop()
    this.ctx?.close()
    this.ctx = null
    this.master = null
    this.roleGains.clear()
  }

  // --- transport ---

  get isPlaying() { return this.playing }

  private get beatsPerSecond() { return this.tempoBpm / 60 }

  async play(fromBeat?: number) {
    const ctx = this.ensureContext()
    if (ctx.state === 'suspended') await ctx.resume()

    this.stopSources()
    const start = fromBeat ?? this.positionBeats()
    const [, end] = this.activeRange()
    this.cursorBeat = start >= end - 1e-6 ? this.activeRange()[0] : start
    this.cursorTime = ctx.currentTime + 0.06 // small pad so the first hit isn't clipped
    this.segments = []
    this.stopAtTime = null
    this.playing = true

    this.schedule()
    this.timer = window.setInterval(() => this.schedule(), SCHEDULE_MS)
    this.emit()
  }

  stop() {
    if (this.timer !== null) { window.clearInterval(this.timer); this.timer = null }
    const wasPlaying = this.playing
    // Read the playhead before clearing `playing` — once it is false,
    // positionBeats() reports the *scheduling* cursor, which runs a lookahead
    // ahead of what you actually heard.
    const at = this.positionBeats()
    this.playing = false
    this.stopSources()
    this.cursorBeat = at
    this.segments = []
    this.stopAtTime = null
    if (wasPlaying) this.emit()
  }

  async toggle(fromBeat?: number) {
    if (this.playing) this.stop()
    else await this.play(fromBeat)
  }

  seek(beat: number) {
    const [lo, hi] = this.activeRange()
    const target = Math.min(Math.max(beat, lo), hi)
    if (this.playing) void this.play(target)
    else { this.cursorBeat = target; this.emit() }
  }

  setLoop(range: { start: number; end: number } | null) {
    this.loopRange = range && range.end > range.start ? range : null
    if (this.loopRange) {
      const { start, end } = this.loopRange
      const at = this.positionBeats()
      if (at < start || at >= end) this.seek(start)
      else if (this.playing) void this.play(at) // re-arm the scheduler on the new range
    }
    this.emit()
  }

  get loop() { return this.loopRange }

  private activeRange(): [number, number] {
    if (this.loopRange) return [this.loopRange.start, this.loopRange.end]
    return [0, this.songEndBeat]
  }

  // --- mixing ---

  setMuted(role: string, value: boolean) {
    if (value) this.muted.add(role); else this.muted.delete(role)
    this.emit()
  }

  setSoloed(role: string, value: boolean) {
    if (value) this.soloed.add(role); else this.soloed.delete(role)
    this.emit()
  }

  clearSolo() { this.soloed.clear(); this.emit() }

  isMuted(role: string) { return this.muted.has(role) }
  isSoloed(role: string) { return this.soloed.has(role) }
  get anySolo() { return this.soloed.size > 0 }

  private audible(role: string) {
    if (this.soloed.size > 0) return this.soloed.has(role)
    return !this.muted.has(role)
  }

  // --- position ---

  positionBeats(): number {
    if (!this.playing || !this.ctx) return this.cursorBeat
    const now = this.ctx.currentTime
    for (const seg of this.segments) {
      if (now >= seg.startTime && now < seg.endTime) {
        return seg.startBeat + (now - seg.startTime) * this.beatsPerSecond
      }
    }
    // Before the first segment starts, or past the last one.
    const first = this.segments[0]
    if (first && now < first.startTime) return first.startBeat
    const last = this.segments[this.segments.length - 1]
    return last ? last.startBeat + (last.endTime - last.startTime) * this.beatsPerSecond : this.cursorBeat
  }

  private emit() {
    this.onStateChange?.({ playing: this.playing, positionBeats: this.positionBeats() })
  }

  // --- scheduling ---

  private schedule() {
    const ctx = this.ctx
    if (!ctx || !this.playing) return

    if (this.stopAtTime !== null && ctx.currentTime >= this.stopAtTime) {
      this.stop()
      return
    }

    const horizon = ctx.currentTime + LOOKAHEAD_S
    const [lo, hi] = this.activeRange()

    let guard = 0
    while (this.cursorTime < horizon && this.stopAtTime === null && guard++ < 200) {
      const remaining = hi - this.cursorBeat
      if (remaining <= 1e-6) {
        if (this.loopRange) { this.cursorBeat = lo; continue }
        this.stopAtTime = this.cursorTime
        break
      }
      const chunk = Math.min(CHUNK_BEATS, remaining)
      this.scheduleWindow(this.cursorBeat, this.cursorBeat + chunk, this.cursorTime)
      this.segments.push({
        startTime: this.cursorTime,
        endTime: this.cursorTime + chunk / this.beatsPerSecond,
        startBeat: this.cursorBeat,
      })
      this.cursorBeat += chunk
      this.cursorTime += chunk / this.beatsPerSecond
    }

    // Drop segments and finished sources that are safely in the past.
    const cutoff = ctx.currentTime - 1
    this.segments = this.segments.filter((s) => s.endTime > cutoff)
    this.live = this.live.filter((n) => (n as OscillatorNode & { _endsAt?: number })._endsAt === undefined
      || (n as OscillatorNode & { _endsAt?: number })._endsAt! > cutoff)
  }

  private scheduleWindow(beatFrom: number, beatTo: number, timeAtFrom: number) {
    for (const track of this.tracks) {
      const role = track.role ?? 'pad'
      if (!this.audible(role)) continue
      // Notes are sorted by start; walk from the first at or after beatFrom.
      let i = lowerBound(track.notes, beatFrom)
      for (; i < track.notes.length; i++) {
        const note = track.notes[i]
        if (note.start >= beatTo) break
        const at = timeAtFrom + (note.start - beatFrom) / this.beatsPerSecond
        if (role === 'drums') this.fireDrum(note.pitch, note.velocity, at)
        else this.fireTone(role, note.pitch, note.velocity, note.duration, at)
      }
    }
  }

  // --- synthesis ---

  private fireTone(role: string, pitch: number, velocity: number, durBeats: number, at: number) {
    const ctx = this.ctx!
    const voice = TONE_VOICES[role] ?? FALLBACK_VOICE
    const dur = Math.min(durBeats / this.beatsPerSecond, voice.maxSustain)
    const level = (velocity / 127) * voice.gain

    const env = ctx.createGain()
    env.gain.setValueAtTime(0.0001, at)
    env.gain.exponentialRampToValueAtTime(Math.max(level, 0.0002), at + voice.attack)
    // Slight decay across the note, then a release tail — enough shape that
    // sustained pads and short chops don't sound like the same instrument.
    env.gain.setTargetAtTime(level * 0.72, at + voice.attack, Math.max(dur * 0.5, 0.05))
    env.gain.setTargetAtTime(0.0001, at + dur, voice.release / 3)

    const filter = ctx.createBiquadFilter()
    filter.type = voice.filterType
    filter.frequency.value = voice.filterHz
    filter.Q.value = 0.8

    const panner = ctx.createStereoPanner()
    panner.pan.value = voice.pan

    env.connect(filter)
    filter.connect(panner)
    panner.connect(this.roleGain(role))

    const endsAt = at + dur + voice.release + 0.1
    for (const spec of voice.oscillators) {
      const osc = ctx.createOscillator()
      osc.type = spec.type
      osc.frequency.value = midiToHz(pitch)
      osc.detune.value = spec.detune
      const mix = ctx.createGain()
      mix.gain.value = spec.gain
      osc.connect(mix)
      mix.connect(env)
      osc.start(at)
      osc.stop(endsAt)
      this.track(osc, endsAt)
    }
  }

  private fireDrum(pitch: number, velocity: number, at: number) {
    const ctx = this.ctx!
    const spec = drumFor(pitch) ?? DEFAULT_DRUM
    const level = (velocity / 127) * spec.gain * 0.5

    const panner = ctx.createStereoPanner()
    panner.pan.value = spec.pan
    panner.connect(this.roleGain('drums'))

    const env = ctx.createGain()
    env.gain.setValueAtTime(level, at)
    env.gain.exponentialRampToValueAtTime(0.0001, at + spec.decay)
    env.connect(panner)

    const endsAt = at + spec.decay + 0.05

    if (spec.kind === 'kick' || spec.kind === 'tom') {
      // Pitched body with a downward sweep — the sweep is what reads as "drum"
      // rather than "short bass note".
      const osc = ctx.createOscillator()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(spec.hz * (spec.kind === 'kick' ? 2.6 : 1.6), at)
      osc.frequency.exponentialRampToValueAtTime(spec.hz * 0.6, at + spec.decay * 0.85)
      osc.connect(env)
      osc.start(at)
      osc.stop(endsAt)
      this.track(osc, endsAt)

      if (spec.kind === 'kick') { // a click so it cuts through on laptop speakers
        this.noiseBurst(at, 0.012, 'highpass', 3000, level * 0.5, panner)
      }
      return
    }

    if (spec.kind === 'bell') {
      for (const mult of [1, 1.48]) {
        const osc = ctx.createOscillator()
        osc.type = 'square'
        osc.frequency.value = spec.hz * mult
        const g = ctx.createGain()
        g.gain.value = 0.5
        osc.connect(g)
        g.connect(env)
        osc.start(at)
        osc.stop(endsAt)
        this.track(osc, endsAt)
      }
      return
    }

    if (spec.kind === 'snare') {
      // Noise for the wires, a short tone for the shell.
      this.noiseBurst(at, spec.decay, 'bandpass', spec.hz, level, panner)
      const osc = ctx.createOscillator()
      osc.type = 'triangle'
      osc.frequency.setValueAtTime(240, at)
      osc.frequency.exponentialRampToValueAtTime(160, at + spec.decay * 0.6)
      const g = ctx.createGain()
      g.gain.setValueAtTime(level * 0.5, at)
      g.gain.exponentialRampToValueAtTime(0.0001, at + spec.decay * 0.7)
      osc.connect(g)
      g.connect(panner)
      osc.start(at)
      osc.stop(endsAt)
      this.track(osc, endsAt)
      return
    }

    if (spec.kind === 'perc' && spec.hz < 600) {
      // Low percussion (congas, bongos, timbales) is mostly pitch.
      const osc = ctx.createOscillator()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(spec.hz * 1.3, at)
      osc.frequency.exponentialRampToValueAtTime(spec.hz * 0.8, at + spec.decay)
      osc.connect(env)
      osc.start(at)
      osc.stop(endsAt)
      this.track(osc, endsAt)
      this.noiseBurst(at, Math.min(spec.decay, 0.05), 'bandpass', 1800, level * 0.35, panner)
      return
    }

    // Hats, cymbals, high percussion — filtered noise.
    const type: BiquadFilterType = spec.kind === 'perc' ? 'bandpass' : 'highpass'
    this.noiseBurst(at, spec.decay, type, spec.hz, level, panner)
  }

  private noiseBurst(
    at: number, decay: number, filterType: BiquadFilterType,
    hz: number, level: number, dest: AudioNode,
  ) {
    const ctx = this.ctx!
    const src = ctx.createBufferSource()
    src.buffer = this.noiseBuffer
    const filter = ctx.createBiquadFilter()
    filter.type = filterType
    filter.frequency.value = hz
    filter.Q.value = filterType === 'bandpass' ? 1.4 : 0.7
    const g = ctx.createGain()
    g.gain.setValueAtTime(Math.max(level, 0.0002), at)
    g.gain.exponentialRampToValueAtTime(0.0001, at + decay)
    src.connect(filter)
    filter.connect(g)
    g.connect(dest)
    const endsAt = at + decay + 0.02
    src.start(at)
    src.stop(endsAt)
    this.track(src, endsAt)
  }

  private track(node: AudioScheduledSourceNode, endsAt: number) {
    ;(node as AudioScheduledSourceNode & { _endsAt?: number })._endsAt = endsAt
    this.live.push(node)
  }

  private stopSources() {
    for (const node of this.live) {
      try { node.stop() } catch { /* already stopped */ }
    }
    this.live = []
  }
}

/** Index of the first note with start >= beat. Notes must be sorted by start. */
function lowerBound(notes: { start: number }[], beat: number): number {
  let lo = 0
  let hi = notes.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (notes[mid].start < beat) lo = mid + 1
    else hi = mid
  }
  return lo
}
