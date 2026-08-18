import type { Role, Section } from '../types'
import { ROLE_LABELS } from '../types'

interface Props {
  roles: Role[]
  noteCounts: Record<string, number>
  section: Section | undefined
  isMuted: (role: string) => boolean
  isSoloed: (role: string) => boolean
  anySolo: boolean
  onMute: (role: string, value: boolean) => void
  onSolo: (role: string, value: boolean) => void
}

/**
 * The reason this UI exists at all: mute the lead, hit play, pick up the guitar.
 * Everything else here is navigation — this is the part you actually use.
 */
export function RoleRack({
  roles, noteCounts, section, isMuted, isSoloed, anySolo, onMute, onSolo,
}: Props) {
  const skipped = new Set(section?.skip_roles ?? [])

  return (
    <div className="rack">
      <div className="panel-head">
        <h2>Layers</h2>
        {anySolo && <span className="solo-flag">solo active</span>}
      </div>

      <ul className="rack-list">
        {roles.map((role) => {
          const muted = isMuted(role)
          const soloed = isSoloed(role)
          const silentHere = skipped.has(role)
          const audible = anySolo ? soloed : !muted
          return (
            <li key={role} className={`rack-row${audible ? '' : ' is-quiet'}`}>
              <span className="rack-name">
                {ROLE_LABELS[role] ?? role}
                {silentHere && (
                  <span className="rack-skip" title="skip_roles — this layer is out for the selected section">
                    out
                  </span>
                )}
              </span>
              <span className="rack-count">{noteCounts[role] ?? 0}</span>
              <span className="rack-buttons">
                <button
                  className={`pill${muted ? ' pill-mute-on' : ''}`}
                  onClick={() => onMute(role, !muted)}
                  title="Mute this layer"
                >M</button>
                <button
                  className={`pill${soloed ? ' pill-solo-on' : ''}`}
                  onClick={() => onSolo(role, !soloed)}
                  title="Solo this layer"
                >S</button>
              </span>
            </li>
          )
        })}
      </ul>

      {roles.length === 0 && <p className="empty">No roles in this spec.</p>}
    </div>
  )
}
