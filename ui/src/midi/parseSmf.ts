/**
 * Minimal Standard MIDI File reader — enough for what composer.py writes.
 *
 * We deliberately play back the real full.mid rather than re-synthesising the
 * spec in TypeScript. Re-implementing voice_bass / feel_hits / the drum
 * patterns here would drift from composer.py the moment either side changed,
 * and then the UI would be lying about what landed on disk. Parsing the actual
 * file means what you hear is what your DAW will open.
 *
 * composer.py writes type-1 files with one named track per role ("full-bass",
 * "full-drums", …) at PPQN 960, no running status. We still handle running
 * status and skip unknown events, so hand-edited or third-party MIDI in the
 * archive degrades to "plays anyway" instead of throwing.
 */

export interface MidiNote {
  /** Onset in beats (quarter notes) from the start of the file. */
  start: number
  /** Duration in beats. */
  duration: number
  pitch: number
  velocity: number
}

export interface MidiTrack {
  name: string
  /** Role parsed out of composer.py's "full-<role>" track naming, when present. */
  role: string | null
  notes: MidiNote[]
}

export interface ParsedMidi {
  ppqn: number
  tempoBpm: number
  timeSig: [number, number]
  tracks: MidiTrack[]
  totalBeats: number
}

class Reader {
  private pos = 0
  constructor(private view: DataView) {}

  get offset() { return this.pos }
  get done() { return this.pos >= this.view.byteLength }

  u8() { return this.view.getUint8(this.pos++) }
  u16() { const v = this.view.getUint16(this.pos); this.pos += 2; return v }
  u32() { const v = this.view.getUint32(this.pos); this.pos += 4; return v }

  peek() { return this.view.getUint8(this.pos) }
  skip(n: number) { this.pos += n }
  seek(n: number) { this.pos = n }

  ascii(n: number) {
    let s = ''
    for (let i = 0; i < n; i++) s += String.fromCharCode(this.u8())
    return s
  }

  bytes(n: number) {
    const out = new Uint8Array(n)
    for (let i = 0; i < n; i++) out[i] = this.u8()
    return out
  }

  /** Variable-length quantity. */
  vlq() {
    let value = 0
    for (let i = 0; i < 4; i++) {
      const b = this.u8()
      value = (value << 7) | (b & 0x7f)
      if ((b & 0x80) === 0) break
    }
    return value
  }
}

const decoder = new TextDecoder('utf-8')

function roleFromTrackName(name: string): string | null {
  // composer.py names tracks "full-<role>" in full.mid and "<section>-<role>"
  // in the per-section files. Both put the role last.
  const m = /^(?:full|.+)-([a-z_]+)$/.exec(name.trim())
  return m ? m[1] : null
}

export function parseSmf(buffer: ArrayBuffer): ParsedMidi {
  const r = new Reader(new DataView(buffer))

  if (r.ascii(4) !== 'MThd') throw new Error('not a MIDI file (missing MThd)')
  const headerLen = r.u32()
  const headerEnd = r.offset + headerLen
  r.u16() // format — we treat 0 and 1 the same way
  const trackCount = r.u16()
  const division = r.u16()
  r.seek(headerEnd)

  if (division & 0x8000) throw new Error('SMPTE time division is not supported')
  const ppqn = division || 960

  let tempoBpm = 120
  let timeSig: [number, number] = [4, 4]
  const tracks: MidiTrack[] = []
  let totalTicks = 0

  for (let t = 0; t < trackCount && !r.done; t++) {
    const magic = r.ascii(4)
    const len = r.u32()
    const chunkEnd = r.offset + len
    if (magic !== 'MTrk') { r.seek(chunkEnd); continue }

    let tick = 0
    let runningStatus = 0
    let name = ''
    const notes: MidiNote[] = []
    // Pitch -> stack of open note-ons, so repeated notes at the same pitch pair
    // up in order rather than clobbering each other.
    const open = new Map<number, { start: number; velocity: number }[]>()

    while (r.offset < chunkEnd) {
      tick += r.vlq()

      let status = r.peek()
      if (status & 0x80) { r.skip(1); runningStatus = status } else { status = runningStatus }
      if (!status) break // desynced; abandon this track rather than loop forever

      if (status === 0xff) {
        const type = r.u8()
        const len2 = r.vlq()
        const data = r.bytes(len2)
        if (type === 0x03) {
          name = decoder.decode(data)
        } else if (type === 0x51 && len2 === 3) {
          const micros = (data[0] << 16) | (data[1] << 8) | data[2]
          if (micros > 0) tempoBpm = 60_000_000 / micros
        } else if (type === 0x58 && len2 >= 2) {
          timeSig = [data[0], 2 ** data[1]]
        }
        if (type === 0x2f) break // end of track
        continue
      }

      if (status === 0xf0 || status === 0xf7) { // sysex — skip payload
        const len2 = r.vlq()
        r.skip(len2)
        continue
      }

      const kind = status & 0xf0
      if (kind === 0x90 || kind === 0x80) {
        const pitch = r.u8()
        const velocity = r.u8()
        const isOn = kind === 0x90 && velocity > 0
        if (isOn) {
          const stack = open.get(pitch) ?? []
          stack.push({ start: tick, velocity })
          open.set(pitch, stack)
        } else {
          const stack = open.get(pitch)
          const started = stack?.shift()
          if (started) {
            notes.push({
              start: started.start / ppqn,
              duration: Math.max(tick - started.start, 1) / ppqn,
              pitch,
              velocity: started.velocity,
            })
          }
        }
      } else if (kind === 0xc0 || kind === 0xd0) {
        r.skip(1) // 1-byte messages
      } else {
        r.skip(2) // control change, pitch bend, aftertouch
      }
    }

    // Anything still held at end-of-track gets a nominal 1-beat tail.
    for (const [pitch, stack] of open) {
      for (const started of stack) {
        notes.push({
          start: started.start / ppqn,
          duration: 1,
          pitch,
          velocity: started.velocity,
        })
      }
    }

    notes.sort((a, b) => a.start - b.start)
    totalTicks = Math.max(totalTicks, tick)
    r.seek(chunkEnd)

    if (notes.length === 0 && !name) continue // meta-only track (tempo map)
    tracks.push({ name, role: roleFromTrackName(name), notes })
  }

  return { ppqn, tempoBpm, timeSig, tracks, totalBeats: totalTicks / ppqn }
}
