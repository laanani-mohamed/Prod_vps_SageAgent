import type { CSSProperties, ReactNode } from 'react'
import { api, estCollaborateur, session } from '../lib/api'
import { dateHeure, nomCommercial, surCouleur } from '../lib/format'
import Menu from './Menu'

/** Cadre d'une page : menu + contenu, dans le thème de la section (`accent` remplace sa couleur principale).
 *  Menu : dernière ingestion ETL du client et, pour un collaborateur, son nom (fiche Sage de son co_no). */
export default async function Page({ theme = 'ardoise', accent, children }: { theme?: string; accent?: string; children: ReactNode }) {
  const s = await session()
  const collab = estCollaborateur(s)
  const [maj, moi] = await Promise.all([   // facultatifs : la page s'affiche même si l'un échoue
    api(`/api/bi/dashboard/last-update?client_schema=${encodeURIComponent(s.client ?? '')}`).catch(() => null),
    collab && s.coNo ? api('/api/referentiel/collaborateurs', { client_schema: s.client, co_no: [s.coNo] }).catch(() => null) : null,
  ])
  const style = accent ? ({ '--accent': accent, '--sur-accent': surCouleur(accent) } as CSSProperties) : undefined
  return (
    <div className={`appli theme-${theme}`} style={style}>
      <Menu client={s.client} collaborateur={collab} nom={moi?.data?.[0] ? nomCommercial(moi.data[0]) : null} miseAJour={dateHeure(maj?.last_update)} />
      <main className="contenu">{children}</main>
    </div>
  )
}
