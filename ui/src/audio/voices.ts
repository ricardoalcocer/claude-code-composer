/**
 * Voice definitions — a deliberately cheap synth, one timbre per composer role.
 *
 * This is not trying to sound good. It is trying to let you tell, in two
 * seconds and without opening a DAW, whether a sketch is worth opening in a
 * DAW. Roles get distinct enough timbres and stereo positions that you can
 * pick the bass out from the rhythm guitars and hear what soloing the drums
 * does — that's the whole bar.
 */

export interface ToneVoice {
  kind: 'tone'
  /** Oscillators layered per note; detune is in cents. */
  oscillators: { type: OscillatorType; detune: number; gain: number }[]
  filterType: BiquadFilterType
  filterHz: number
  attack: number
  release: number
  /** Cap on how long a note rings, in seconds. Keeps pads from smearing. */
  maxSustain: number
  gain: number
  pan: number
}

export const TONE_VOICES: Record<string, ToneVoice> = {
  bass: {
    kind: 'tone',
    oscillators: [{ type: 'sawtooth', detune: 0, gain: 1 }, { type: 'sine', detune: 0, gain: 0.6 }],
    filterType: 'lowpass', filterHz: 620,
    attack: 0.006, release: 0.09, maxSustain: 4,
    gain: 0.34, pan: 0,
  },
  pad: {
    kind: 'tone',
    oscillators: [
      { type: 'triangle', detune: -6, gain: 1 },
      { type: 'triangle', detune: 7, gain: 1 },
    ],
    filterType: 'lowpass', filterHz: 2000,
    attack: 0.09, release: 0.34, maxSustain: 8,
    gain: 0.11, pan: 0,
  },
  synth_pad: {
    kind: 'tone',
    oscillators: [
      { type: 'sawtooth', detune: -9, gain: 0.6 },
      { type: 'triangle', detune: 9, gain: 1 },
    ],
    filterType: 'lowpass', filterHz: 1500,
    attack: 0.18, release: 0.5, maxSustain: 10,
    gain: 0.09, pan: 0,
  },
  rhy_l: {
    kind: 'tone',
    oscillators: [{ type: 'square', detune: 0, gain: 1 }],
    filterType: 'lowpass', filterHz: 2100,
    attack: 0.004, release: 0.07, maxSustain: 2,
    gain: 0.085, pan: -0.62,
  },
  rhy_r: {
    kind: 'tone',
    oscillators: [{ type: 'square', detune: 4, gain: 1 }],
    filterType: 'lowpass', filterHz: 2100,
    attack: 0.004, release: 0.07, maxSustain: 2,
    gain: 0.085, pan: 0.62,
  },
  clean: {
    kind: 'tone',
    oscillators: [{ type: 'triangle', detune: 0, gain: 1 }],
    filterType: 'lowpass', filterHz: 3200,
    attack: 0.004, release: 0.22, maxSustain: 3,
    gain: 0.17, pan: -0.25,
  },
  strum: {
    kind: 'tone',
    oscillators: [{ type: 'triangle', detune: 0, gain: 1 }, { type: 'sawtooth', detune: 6, gain: 0.35 }],
    filterType: 'lowpass', filterHz: 2600,
    attack: 0.006, release: 0.3, maxSustain: 4,
    gain: 0.13, pan: 0.25,
  },
  lead: {
    kind: 'tone',
    oscillators: [{ type: 'sawtooth', detune: 0, gain: 1 }, { type: 'square', detune: -5, gain: 0.3 }],
    filterType: 'lowpass', filterHz: 3400,
    attack: 0.012, release: 0.2, maxSustain: 6,
    gain: 0.2, pan: 0,
  },
  chugg: {
    kind: 'tone',
    oscillators: [{ type: 'sawtooth', detune: 0, gain: 1 }],
    filterType: 'lowpass', filterHz: 420,
    attack: 0.002, release: 0.05, maxSustain: 0.4,
    gain: 0.3, pan: 0,
  },
}

export const FALLBACK_VOICE = TONE_VOICES.pad

// --- drums -----------------------------------------------------------------

export type DrumKind = 'kick' | 'snare' | 'hat' | 'openhat' | 'cymbal' | 'tom' | 'bell' | 'perc'

export interface DrumSpec {
  kind: DrumKind
  label: string
  /** Base frequency: pitch centre for tonal hits, filter centre for noise hits. */
  hz: number
  decay: number
  gain: number
  pan: number
}

/** GM percussion map, covering every pitch composer.py's GM_DRUMS emits. */
export const DRUM_MAP: Record<number, DrumSpec> = {
  35: { kind: 'kick', label: 'Kick (acoustic)', hz: 105, decay: 0.24, gain: 1.0, pan: 0 },
  36: { kind: 'kick', label: 'Kick', hz: 120, decay: 0.2, gain: 1.0, pan: 0 },
  37: { kind: 'perc', label: 'Side stick', hz: 2200, decay: 0.05, gain: 0.5, pan: -0.1 },
  38: { kind: 'snare', label: 'Snare', hz: 1750, decay: 0.17, gain: 0.85, pan: 0 },
  39: { kind: 'perc', label: 'Hand clap', hz: 1500, decay: 0.14, gain: 0.6, pan: 0.15 },
  40: { kind: 'snare', label: 'Snare (electric)', hz: 1900, decay: 0.15, gain: 0.85, pan: 0 },
  41: { kind: 'tom', label: 'Floor tom', hz: 90, decay: 0.32, gain: 0.8, pan: -0.3 },
  42: { kind: 'hat', label: 'Closed hi-hat', hz: 9000, decay: 0.038, gain: 0.4, pan: 0.22 },
  43: { kind: 'tom', label: 'Tom (low)', hz: 105, decay: 0.3, gain: 0.8, pan: -0.28 },
  44: { kind: 'hat', label: 'Pedal hi-hat', hz: 8000, decay: 0.05, gain: 0.32, pan: 0.22 },
  45: { kind: 'tom', label: 'Tom (low-mid)', hz: 130, decay: 0.28, gain: 0.8, pan: -0.14 },
  46: { kind: 'openhat', label: 'Open hi-hat', hz: 7500, decay: 0.3, gain: 0.38, pan: 0.22 },
  47: { kind: 'tom', label: 'Tom (mid)', hz: 160, decay: 0.26, gain: 0.8, pan: 0 },
  48: { kind: 'tom', label: 'Tom (hi-mid)', hz: 195, decay: 0.24, gain: 0.8, pan: 0.14 },
  49: { kind: 'cymbal', label: 'Crash', hz: 5200, decay: 1.3, gain: 0.5, pan: -0.35 },
  50: { kind: 'tom', label: 'Tom (high)', hz: 235, decay: 0.22, gain: 0.8, pan: 0.28 },
  51: { kind: 'cymbal', label: 'Ride', hz: 6800, decay: 0.55, gain: 0.34, pan: 0.35 },
  52: { kind: 'cymbal', label: 'China', hz: 4200, decay: 1.0, gain: 0.45, pan: -0.4 },
  53: { kind: 'bell', label: 'Ride bell', hz: 1050, decay: 0.4, gain: 0.4, pan: 0.35 },
  54: { kind: 'perc', label: 'Tambourine', hz: 9500, decay: 0.1, gain: 0.34, pan: 0.3 },
  55: { kind: 'cymbal', label: 'Splash', hz: 6000, decay: 0.7, gain: 0.4, pan: 0.3 },
  56: { kind: 'bell', label: 'Cowbell', hz: 810, decay: 0.16, gain: 0.45, pan: -0.2 },
  57: { kind: 'cymbal', label: 'Crash 2', hz: 4800, decay: 1.2, gain: 0.48, pan: 0.35 },
  59: { kind: 'cymbal', label: 'Ride 2', hz: 6400, decay: 0.5, gain: 0.34, pan: 0.3 },
  60: { kind: 'perc', label: 'Bongo (hi)', hz: 330, decay: 0.14, gain: 0.55, pan: 0.3 },
  61: { kind: 'perc', label: 'Bongo (lo)', hz: 230, decay: 0.16, gain: 0.55, pan: 0.3 },
  62: { kind: 'perc', label: 'Conga (mute)', hz: 300, decay: 0.11, gain: 0.5, pan: -0.3 },
  63: { kind: 'perc', label: 'Conga (open)', hz: 245, decay: 0.24, gain: 0.6, pan: -0.3 },
  64: { kind: 'perc', label: 'Conga (low)', hz: 175, decay: 0.28, gain: 0.6, pan: -0.3 },
  65: { kind: 'perc', label: 'Timbale (hi)', hz: 400, decay: 0.18, gain: 0.55, pan: 0.25 },
  66: { kind: 'perc', label: 'Timbale (lo)', hz: 310, decay: 0.2, gain: 0.55, pan: 0.25 },
  70: { kind: 'perc', label: 'Maracas', hz: 10000, decay: 0.06, gain: 0.3, pan: 0.35 },
  75: { kind: 'perc', label: 'Claves', hz: 2500, decay: 0.08, gain: 0.5, pan: -0.25 },
  76: { kind: 'perc', label: 'Woodblock (hi)', hz: 2300, decay: 0.09, gain: 0.5, pan: -0.25 },
  77: { kind: 'perc', label: 'Woodblock (lo)', hz: 1800, decay: 0.1, gain: 0.5, pan: -0.25 },
}

export const DEFAULT_DRUM: DrumSpec =
  { kind: 'perc', label: 'Percussion', hz: 1200, decay: 0.12, gain: 0.45, pan: 0 }

export function drumFor(pitch: number): DrumSpec {
  return DRUM_MAP[pitch] ?? DEFAULT_DRUM
}

/** MIDI pitch → Hz, A440. */
export function midiToHz(pitch: number): number {
  return 440 * 2 ** ((pitch - 69) / 12)
}

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

/** MIDI pitch → scientific pitch name, e.g. 64 -> "E4". */
export function midiToName(pitch: number): string {
  return `${NOTE_NAMES[((pitch % 12) + 12) % 12]}${Math.floor(pitch / 12) - 1}`
}
