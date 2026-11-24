'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'
import { useFormStatus } from 'react-dom'
import { deconnexion } from '../app/actions'
import { RAPPORTS } from '../lib/rapports'
import { Attente } from './Interactions'

// Icônes au trait (grille 24, trait 1,5) : une par entrée du menu.
const ICONES = {
  tableau: <><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></>,
  base: <><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" /></>,
  ventes: <><path d="M22 7l-8.5 8.5-5-5L2 17" /><path d="M16 7h6v6" /></>,
  achats: <><circle cx="8" cy="21" r="1" /><circle cx="19" cy="21" r="1" /><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" /></>,
  stock: <><path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z" /><path d="M12 22V12" /><path d="M3.3 7l7.7 4.73a2 2 0 0 0 2 0L20.7 7" /></>,
  reglements: <><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" /><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" /></>,
  commande: <><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="M12 11h4M12 16h4M8 11h.01M8 16h.01" /></>,
  depot: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M17 8l-5-5-5 5" /><path d="M12 3v12" /></>,
}

// `directeur` : page refusée au collaborateur (marquée 🚫).
const PAGES = [
  { nom: 'Tableau de bord', href: '/', base: '/', icone: ICONES.tableau },
  { nom: 'Fichier de base', href: '/fichier-de-base/articles', base: '/fichier-de-base', icone: ICONES.base },
  { nom: 'Ventes', href: '/ventes', base: '/ventes', icone: ICONES.ventes },
  { nom: 'Achats', href: '/achats', base: '/achats', icone: ICONES.achats, directeur: true },
  { nom: 'Stock et mouvements', href: '/stock/plan', base: '/stock', icone: ICONES.stock, directeur: true },
  { nom: 'Règlements', href: '/reglements/encaissements', base: '/reglements', icone: ICONES.reglements },
]
const ACTIONS = [
  { nom: 'Bon de commande', href: '/bon-de-commande', base: '/bon-de-commande', icone: ICONES.commande },
  { nom: 'Dépôt des fichiers', href: '/depot', base: '/depot', icone: ICONES.depot, directeur: true },
]
const INTERDIT = '🚫'

function Icone({ children }: { children: ReactNode }) {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  )
}

/** Bouton de déconnexion : verrouillé avec un cercle pendant la déconnexion. */
function Sortir() {
  const { pending } = useFormStatus()
  return (
    <button type="submit" className="secondaire large sortir" disabled={pending} aria-busy={pending}>
      {pending && <span className="cercle" aria-hidden="true" />}Se déconnecter
    </button>
  )
}

export default function Menu({ client, collaborateur, nom, miseAJour }: { client: string | null; collaborateur: boolean; nom: string | null; miseAJour: string }) {
  const chemin = usePathname()
  const actif = (base: string) => (base === '/' ? chemin === '/' : chemin.startsWith(base))
  const refus = <span className="interdit" aria-label="Accès refusé">{INTERDIT}</span>

  const entree = (p: (typeof PAGES)[number] | (typeof ACTIONS)[number]) => (
    <Link prefetch={false} key={p.href} href={p.href} className="entree" aria-current={actif(p.base) ? 'page' : undefined}>
      <Icone>{p.icone}</Icone>
      <span className="coupe">{p.nom}</span>
      {collaborateur && 'directeur' in p && refus}
      <Attente />
    </Link>
  )

  return (
    <nav className="menu" aria-label="Navigation">
      <div className="marque">
        <span className="logo">IT</span>BORD
      </div>
      {PAGES.map(entree)}

      <p className="section-menu" id="menu-rapports">Rapports</p>
      <div className="rapports" role="group" aria-labelledby="menu-rapports">
        {RAPPORTS.map((r) => (
          <Link prefetch={false} key={r.n} href={`/rapports/${r.n}`} className="entree" aria-current={chemin === `/rapports/${r.n}` ? 'page' : undefined}>
            <span className="numero">{r.n}</span>
            <span className="coupe">{r.menu}</span>
            {collaborateur && 'stock' in r && refus}
            <Attente />
          </Link>
        ))}
      </div>

      <p className="section-menu" id="menu-actions">Actions</p>
      <div className="rapports" role="group" aria-labelledby="menu-actions">
        {ACTIONS.map(entree)}
      </div>

      <div className="espace" />
      <p className="maj">Dernière mise à jour : <span>{miseAJour}</span></p>
      <div className="utilisateur">
        <span className="avatar">{(client ?? '?').slice(0, 2).toUpperCase()}</span>
        <span className="coupe">
          <strong>{(client ?? '').toUpperCase()}</strong>
          <span className="doux">{collaborateur ? 'Collaborateur' : 'Directeur'}</span>
          {nom && <span className="doux coupe" title={nom}>{nom}</span>}
        </span>
      </div>
      <form action={deconnexion}>
        <Sortir />
      </form>
    </nav>
  )
}
