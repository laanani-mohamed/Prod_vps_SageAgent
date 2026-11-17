import type { CSSProperties, ReactNode } from 'react'
import { estCollaborateur, session } from '../lib/api'
import { surCouleur } from '../lib/format'
import Menu from './Menu'

/** Cadre d'une page : menu + contenu, dans le thème de la section (`accent` remplace sa couleur principale). */
export default async function Page({ theme = 'ardoise', accent, children }: { theme?: string; accent?: string; children: ReactNode }) {
  const s = await session()
  const style = accent ? ({ '--accent': accent, '--sur-accent': surCouleur(accent) } as CSSProperties) : undefined
  return (
    <div className={`appli theme-${theme}`} style={style}>
      <Menu client={s.client} collaborateur={estCollaborateur(s)} />
      <main className="contenu">{children}</main>
    </div>
  )
}
