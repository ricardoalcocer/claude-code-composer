import type {
  AgentJob, Catalog, ComposeResult, LibraryEntry, PromoteResult,
  ServerConfig, SongPayload, Spec, TransformResult,
} from './types'

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    // The bridge answers errors as {"error": "..."} — surface that, not "500".
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.error) detail = body.error
    } catch { /* non-JSON error body; keep statusText */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const getConfig = () => getJSON<ServerConfig>('/api/config')

export const getLibrary = () =>
  getJSON<{ root: string; songs: LibraryEntry[] }>('/api/library')

export const getSong = (rel: string) =>
  getJSON<SongPayload>(`/api/song?rel=${encodeURIComponent(rel)}`)

export const getCatalog = () => getJSON<Catalog>('/api/catalog')

export function fileUrl(rel: string, name: string) {
  return `/api/file?rel=${encodeURIComponent(rel)}&name=${encodeURIComponent(name)}`
}

export async function fetchMidi(rel: string, name: string): Promise<ArrayBuffer> {
  const res = await fetch(fileUrl(rel, name))
  if (!res.ok) throw new Error(`could not load ${name}`)
  return res.arrayBuffer()
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = await res.json()
      if (err?.error) detail = err.error
    } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const transform = (rel: string, op: string, arg?: unknown) =>
  postJSON<TransformResult>('/api/transform', { rel, op, arg })

export const generate = (brief: string, count: number, parent_rel?: string) =>
  postJSON<{ ok: boolean; jobs: AgentJob[] }>('/api/generate', { brief, count, parent_rel })

export const patch = (rel: string, ask: string) =>
  postJSON<{ ok: boolean; job: AgentJob }>('/api/patch', { rel, ask })

export const promote = (rel: string, openInReaper = true) =>
  postJSON<PromoteResult>('/api/promote', { rel, open_in_reaper: openInReaper })

export const discard = (rel: string) =>
  postJSON<{ ok: boolean; binned_to: string }>('/api/discard', { rel })

export const getJobs = () =>
  getJSON<{ jobs: AgentJob[]; claude_available: boolean }>('/api/jobs')

export async function compose(body: {
  spec: Spec
  rel?: string
  dir_name?: string
  parent_rel?: string
  midi_only?: boolean
}): Promise<ComposeResult> {
  const res = await fetch('/api/compose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = await res.json()
      if (err?.error) detail = err.error
    } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json()
}
