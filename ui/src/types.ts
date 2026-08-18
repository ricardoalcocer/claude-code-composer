// Mirrors the spec shape documented in SKILL.md § "Spec field reference".
// Everything optional there is optional here — old specs in the archive predate
// several of these fields and must still load.

export type Role =
  | 'bass' | 'pad' | 'rhy_l' | 'rhy_r' | 'clean'
  | 'strum' | 'lead' | 'chugg' | 'synth_pad' | 'drums'

export const ALL_ROLES: Role[] = [
  'bass', 'pad', 'rhy_l', 'rhy_r', 'clean',
  'strum', 'lead', 'chugg', 'synth_pad', 'drums',
]

export const DEFAULT_ROLES: Role[] = ['bass', 'pad', 'rhy_l', 'rhy_r', 'drums']

export const ROLE_LABELS: Record<Role, string> = {
  bass: 'Bass',
  pad: 'Pad',
  rhy_l: 'Rhythm L',
  rhy_r: 'Rhythm R',
  clean: 'Clean',
  strum: 'Strum',
  lead: 'Lead',
  chugg: 'Chugg',
  synth_pad: 'Synth pad',
  drums: 'Drums',
}

export interface Chord {
  name: string
  beats: number
}

export interface Section {
  name: string
  feel?: string
  drums?: string
  voicing?: string
  move?: string
  scales?: string
  skip_roles?: Role[]
  chords: Chord[]
  melody?: [number, string, number][]
  melody_loop_beats?: number
  chugg?: string
}

export interface Spec {
  song_name?: string
  key?: string
  tempo: number
  time_sig?: [number, number]
  sections: Section[]
  form: string[]
  roles?: Role[]
  auto_fills?: boolean
}

export interface LibraryEntry {
  rel: string
  dir_name: string
  group: string
  key: string | null
  bpm: number | null
  slug: string
  song_name: string | null
  sections: number
  form_length: number
  roles: Role[] | null
  has_rpp: boolean
  has_full_mid: boolean
  mtime: number
  broken?: boolean
}

export interface SongPayload {
  rel: string
  spec: Spec
  files: { name: string; size: number }[]
}

export interface ServerConfig {
  output_root: string
  output_root_exists: boolean
  repo_root: string
  has_config_json: boolean
  composer_present: boolean
}

export interface ComposeResult {
  ok: boolean
  returncode: number
  stdout: string
  stderr: string
  rel: string
  midi_only: boolean
}

export interface CatalogSection {
  title: string
  entries: string[]
}

export interface AgentJob {
  id: string
  kind: 'brief' | 'patch' | 'prime'
  label: string
  status: 'queued' | 'running' | 'done' | 'error'
  detail: string
  rel: string | null
  created: number
  started: number | null
  finished: number | null
  elapsed: number
}

export interface TransformResult {
  ok: boolean
  rel: string
  ms: number
}

export interface PromoteResult {
  ok: boolean
  rpp: string | null
  path: string | null
  opened: boolean
  error?: string
}

export type Catalog = Record<string, CatalogSection>

// --- derived helpers -------------------------------------------------------

export function sectionBeats(section: Section): number {
  return section.chords.reduce((n, c) => n + c.beats, 0)
}

export function specRoles(spec: Spec): Role[] {
  const chosen = new Set(spec.roles ?? DEFAULT_ROLES)
  // Preserve ALL_ROLES ordering — that's the order composer.py writes tracks in.
  return ALL_ROLES.filter((r) => chosen.has(r))
}

/** Form positions with their absolute beat offsets, in playback order. */
export function formTimeline(spec: Spec) {
  const byName = new Map(spec.sections.map((s) => [s.name, s]))
  let cursor = 0
  return spec.form.map((name, index) => {
    const section = byName.get(name)
    const beats = section ? sectionBeats(section) : 0
    const entry = { index, name, section, startBeat: cursor, beats }
    cursor += beats
    return entry
  })
}

export function totalBeats(spec: Spec): number {
  return formTimeline(spec).reduce((n, p) => n + p.beats, 0)
}

/**
 * A distinct hue per section name, so every repeat of a section reads as the
 * same colour and the shape of the form is legible at a glance.
 *
 * Hashing the name looked fine for "verse"/"chorus" and fell apart for the
 * short names real specs actually use — "a" and "b" hash 1 degree apart and
 * render as the same green. Spacing by golden angle over the section's index
 * instead guarantees maximum separation for any set of names, and stays stable
 * because it keys off the spec's own section order.
 */
export function sectionHues(spec: Spec): Map<string, number> {
  const GOLDEN_ANGLE = 137.508
  const hues = new Map<string, number>()
  spec.sections.forEach((s, i) => hues.set(s.name, (20 + i * GOLDEN_ANGLE) % 360))
  // Form entries with no matching section still need a colour to render.
  let extra = spec.sections.length
  for (const name of spec.form) {
    if (!hues.has(name)) hues.set(name, (20 + extra++ * GOLDEN_ANGLE) % 360)
  }
  return hues
}
