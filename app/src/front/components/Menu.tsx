'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useFormStatus } from 'react-dom'
import { deconnexion } from '../app/actions'
import { surCouleur } from '../lib/format'
import { RAPPORTS } from '../lib/rapports'
import { Attente } from './Interactions'

const PAGES = [
  { nom: 'Tableau de Bord', href: '/', base: '/', icone: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z' },
  { nom: 'Fichier de Base', href: '/fichier-de-base/articles', base: '/fichier-de-base', icone: 'M4 5h16v14H4zM4 9h16' },
  { nom: 'Gestion Ventes', href: '/ventes', base: '/ventes', icone: 'M3 12h18M15 6l6 6-6 6' },
  { nom: 'Gestion Achats', href: '/achats', base: '/achats', icone: 'M21 12H3M9 6l-6 6 6 6', directeur: true },
  { nom: 'Stock & Mouvements', href: '/stock/etat', base: '/stock', icone: 'M21 8l-9-5-9 5 9 5zM3 8v8l9 5 9-5V8', directeur: true },
  { nom: 'Règlements', href: '/reglements/encaissements', base: '/reglements', icone: 'M2 6h20v12H2zM12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z' },
]
const INTERDIT = '🚫'

function Icone({ d }: { d: string }) {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d={d} />
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

  return (
    <nav className="menu" aria-label="Navigation">
      <div className="marque">
        <span className="logo">IT</span>BORD
      </div>
      {PAGES.map((p) => (
        <Link prefetch={false} key={p.href} href={p.href} className="entree" aria-current={actif(p.base) ? 'page' : undefined}>
          <Icone d={p.icone} />
          {p.nom}
          {collaborateur && p.directeur && <span className="interdit" aria-label="Accès refusé">{INTERDIT}</span>}
          <Attente />
        </Link>
      ))}
      <div className="entree titre-rapports">
        <Icone d="M7 3h10v18H7zM10 8h4M10 12h4M10 16h2" />
        Rapports
      </div>
      <div className="rapports">
        {RAPPORTS.map((r) => (
          <Link prefetch={false} key={r.n} href={`/rapports/${r.n}`} className="sous-entree" aria-current={chemin === `/rapports/${r.n}` ? 'page' : undefined}>
            <span className="numero" style={{ background: r.couleur, color: surCouleur(r.couleur) }}>{r.n}</span>
            <span className="coupe">{r.menu}</span>
            {collaborateur && 'stock' in r && <span className="interdit" aria-label="Accès refusé">{INTERDIT}</span>}
            <Attente />
          </Link>
        ))}
      </div>
      <Link prefetch={false} href="/bon-de-commande" className="entree" aria-current={chemin.startsWith('/bon-de-commande') ? 'page' : undefined}>
        <Icone d="M6 6h15l-2 9H8zM6 6L5 3H2M10 20a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM19 20a1 1 0 1 1-2 0 1 1 0 0 1 2 0z" />
        Passer bon de commande
        <Attente />
      </Link>
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
