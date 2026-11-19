// Composants d'affichage partagés (rendus côté serveur, sans état).
import Link from 'next/link'
import type { CSSProperties, ReactNode } from 'react'
import { court, entier, pct, surCouleur } from '../lib/format'
import type { Params } from '../lib/params'
import { Attente, CorpsCliquable, FormulaireGet } from './Interactions'

export function Entete({ titre, sur, sousTitre, badge, actions }: {
  titre: string; sur?: string; sousTitre?: ReactNode; badge?: ReactNode; actions?: ReactNode
}) {
  return (
    <header className="entete">
      <div className="titre">
        {badge}
        <div>
          {sur && <div className="sur">{sur}</div>}
          <h1>{titre}</h1>
          {sousTitre && <p className="doux">{sousTitre}</p>}
        </div>
      </div>
      {actions && <div className="actions">{actions}</div>}
    </header>
  )
}

export type Kpi = { nom: string; v: ReactNode; sous?: ReactNode; ton?: 'bon' | 'mauvais' }

/** Tuiles KPI ; `accent` : bordure haute de la couleur de la page (maquettes des rapports). */
export function Kpis({ items, accent }: { items: Kpi[]; accent?: boolean }) {
  return (
    <div className={accent ? 'kpis accent' : 'kpis'} style={{ '--n': items.length } as CSSProperties}>
      {items.map((k) => (
        <div key={k.nom} className="kpi">
          <div className="doux">{k.nom}</div>
          <div className={`valeur ${k.ton ?? ''}`}>{k.v}</div>
          {k.sous && <div className="doux petit">{k.sous}</div>}
        </div>
      ))}
    </div>
  )
}

/** Carte ; dans une grille : `large` = toute la largeur, `span` = nombre de colonnes (2 ou 3). */
export function Carte({ titre, note, large, span, children }: { titre?: ReactNode; note?: ReactNode; large?: boolean; span?: 2 | 3; children: ReactNode }) {
  return (
    <section className={['carte', large && 'large', span && `span-${span}`].filter(Boolean).join(' ')}>
      {(titre || note) && (
        <div className="carte-titre">
          <h2>{titre}</h2>
          {note && <div className="doux">{note}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export type Colonne = { nom: string; droite?: boolean; largeur?: string }
export type Ligne = { cellules: ReactNode[]; href?: string; actif?: boolean; total?: boolean; cle?: string }

/** Tableau ; une ligne avec `href` est cliquable (lien sur la 1re cellule, clic sur toute la ligne : CorpsCliquable).
 *  Liens en prefetch={false} (ici, menu, onglets, pagination) : sinon Next.js calcule à l'avance chaque lien visible
 *  (~40 pages lourdes par affichage) et sature l'API avant le vrai clic. */
export function Tableau({ colonnes, lignes, vide = 'Aucune donnée.' }: { colonnes: Colonne[]; lignes: Ligne[]; vide?: string }) {
  if (!lignes.length) return <p className="vide">{vide}</p>
  const cliquable = lignes.some((l) => l.href)
  const rangees = lignes.map((l, i) => (
    <tr key={l.cle ?? i} className={l.total ? 'total' : l.actif ? 'actif' : undefined} aria-current={l.actif || undefined}>
      {l.cellules.map((c, j) => (
        <td key={j} className={colonnes[j]?.droite ? 'droite' : undefined}>
          {j === 0 && l.href ? <Link prefetch={false} href={l.href} scroll={false}>{c}<Attente /></Link> : c}
        </td>
      ))}
    </tr>
  ))
  return (
    <div className="defile">
      <table className={cliquable ? 'tableau cliquable' : 'tableau'}>
        <colgroup>
          {colonnes.map((c, i) => <col key={i} style={c.largeur ? { width: c.largeur } : undefined} />)}
        </colgroup>
        <thead>
          <tr>{colonnes.map((c, i) => <th key={i} scope="col" className={c.droite ? 'droite' : undefined}>{c.nom}</th>)}</tr>
        </thead>
        {cliquable ? <CorpsCliquable>{rangees}</CorpsCliquable> : <tbody>{rangees}</tbody>}
      </table>
    </div>
  )
}

/** Barres horizontales : longueur proportionnelle à la plus grande valeur. */
export function Barres({ items }: { items: { nom: string; v: number; libelle: string; couleur?: string }[] }) {
  if (!items.length) return <p className="vide">Aucune donnée.</p>
  const max = Math.max(...items.map((i) => Math.abs(i.v)), 1)
  return (
    <ul className="barres">
      {items.map((i, k) => (
        <li key={`${i.nom}-${k}`}>
          <span className="coupe" title={i.nom}>{i.nom}</span>
          <span className="piste"><span style={{ width: `${Math.max(1.5, (Math.abs(i.v) / max) * 100)}%`, background: i.couleur }} /></span>
          <span className="droite fort">{i.libelle}</span>
        </li>
      ))}
    </ul>
  )
}

/** Colonnes verticales : série `b` (couleur de la page), et `a` en gris pour la comparer (période de référence). */
export function Colonnes({ groupes, legende }: { groupes: { nom: string; a?: number | null; b: number }[]; legende: { a?: string; b: string } }) {
  const max = Math.max(...groupes.flatMap((g) => [g.a ?? 0, g.b]), 1)
  const barre = (v: number, cls: string) => (
    <span className={`col ${cls}`}>
      <small>{court(v).replace(' MMAD', ' M').replace(' KMAD', ' K').replace(' DH', '')}</small>
      <span style={{ height: `${Math.max(1, (v / max) * 100)}%` }} />
    </span>
  )
  return (
    <figure className="colonnes">
      <figcaption className="legende">
        {legende.a && <span><i className="a" />{legende.a}</span>}
        <span><i className="b" />{legende.b}</span>
      </figcaption>
      <div className="zone">
        {groupes.map((g) => (
          <div key={g.nom} className="groupe">
            <div className="paire">{g.a != null && barre(g.a, 'a')}{barre(g.b, 'b')}</div>
            <span className="nom coupe" title={g.nom}>{g.nom}</span>
          </div>
        ))}
      </div>
    </figure>
  )
}

/** Barre empilée (part de chaque segment dans le total) et sa légende. */
export function Pile({ segments }: { segments: { nom: string; v: number; couleur: string; libelle: string }[] }) {
  const total = segments.reduce((s, x) => s + Math.max(0, x.v), 0) || 1
  const part = (v: number) => (Math.max(0, v) / total) * 100
  return (
    <div className="pile">
      <div className="barre-pile" role="img" aria-label={segments.map((s) => `${s.nom} : ${pct(part(s.v))}`).join(', ')}>
        {segments.map((s) => (
          <span key={s.nom} style={{ width: `${part(s.v)}%`, background: s.couleur, color: surCouleur(s.couleur) }}>
            {part(s.v) > 6 ? pct(part(s.v)) : ''}
          </span>
        ))}
      </div>
      <ul className="legende-pile">
        {segments.map((s) => (
          <li key={s.nom}>
            <i style={{ background: s.couleur }} />
            <span><span className="doux">{s.nom}</span><strong>{s.libelle}</strong> <span className="doux">· {pct(part(s.v))}</span></span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Onglets (liens) ; `pleineLargeur` : une seule ligne sur toute la largeur, nombre sous le nom (types de documents). */
export function Onglets({ items, pleineLargeur }: { items: { nom: string; href: string; actif: boolean; interdit?: boolean; nombre?: number }[]; pleineLargeur?: boolean }) {
  return (
    <nav className={pleineLargeur ? 'onglets pleine-largeur' : 'onglets'} aria-label="Sections">
      {items.map((o) => (
        <Link prefetch={false} key={o.href} href={o.href} aria-current={o.actif ? 'page' : undefined} scroll={false}>
          {o.interdit && '🚫 '}{o.nom}<Attente />
          {o.nombre != null && <span className="pastille">{entier(o.nombre)}</span>}
        </Link>
      ))}
    </nav>
  )
}

export function Interdit() {
  return <div className="carte refus" role="alert">🚫 Vous n&apos;avez pas les droits nécessaires pour consulter cette section.</div>
}

export function Pagination({ total, page, taille, href }: { total: number; page: number; taille: number; href: (p: number) => string }) {
  const pages = Math.ceil(total / taille)
  if (pages <= 1) return null
  return (
    <nav className="pagination" aria-label="Pages">
      {page > 1 ? <Link prefetch={false} href={href(page - 1)} scroll={false}>‹ Précédente<Attente /></Link> : <span />}
      <span className="doux">Page {page} sur {pages} · {entier(total)} lignes</span>
      {page < pages ? <Link prefetch={false} href={href(page + 1)} scroll={false}>Suivante ›<Attente /></Link> : <span />}
    </nav>
  )
}

/** Formulaire de filtres (GET) : les valeurs partent dans l'URL, la page se recharge côté serveur.
 *  `titre` / `note` : en-tête ; `suite` : seconde ligne (le bouton s'y place) ; `cadre={false}` : dans une carte existante. */
export function Filtres({ children, bouton = 'Appliquer', colonnes, titre, note, suite, cadre = true }: {
  children: ReactNode; bouton?: string; colonnes?: string; titre?: string; note?: string; suite?: ReactNode; cadre?: boolean
}) {
  const valider = <button type="submit" className="principal">{bouton}</button>
  return (
    <FormulaireGet className={cadre ? 'carte bloc-filtres' : 'bloc-filtres'}>
      {titre && <div className="carte-titre"><h2 className="moyen">{titre}</h2>{note && <span className="doux petit">{note}</span>}</div>}
      <div className="filtres" style={colonnes ? { gridTemplateColumns: colonnes } : undefined}>
        {children}
        {!suite && valider}
      </div>
      {suite && <div className="filtres-suite">{suite}{valider}</div>}
    </FormulaireGet>
  )
}

/** Période (du / au) dans un en-tête : formulaire GET qui garde les autres paramètres de l'URL. */
export function Periode({ p, du, au, label = 'Période' }: { p: Params; du: string; au: string; label?: string }) {
  return (
    <FormulaireGet className="periode">
      {Object.entries(p).filter(([k, v]) => typeof v === 'string' && !['du', 'au', 'page'].includes(k)).map(([k, v]) => (
        <input key={k} type="hidden" name={k} value={v as string} />
      ))}
      <span className="doux petit">{label}</span>
      <input type="date" name="du" defaultValue={du} aria-label={`${label} : du`} />
      <span aria-hidden="true">–</span>
      <input type="date" name="au" defaultValue={au} aria-label={`${label} : au`} />
      <button type="submit" className="secondaire">OK</button>
    </FormulaireGet>
  )
}

/** Bloc encadré à l'intérieur d'une carte (fiches du Fichier de base). */
export function SousBloc({ titre, note, children }: { titre: string; note?: string; children: ReactNode }) {
  return (
    <div className="sous-bloc">
      <div className="carte-titre"><h3>{titre}</h3>{note && <span className="doux petit">{note}</span>}</div>
      {children}
    </div>
  )
}

export function Champ({ label, name, defaut, type = 'text', placeholder, options, liste }: {
  label: string; name: string; defaut?: string; type?: string; placeholder?: string; options?: [string, string][]; liste?: string
}) {
  return (
    <label className="champ-filtre">
      <span>{label}</span>
      {options ? (
        <select name={name} defaultValue={defaut}>
          {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      ) : (
        <input name={name} type={type} defaultValue={defaut} placeholder={placeholder} list={liste} min={type === 'number' ? 1 : undefined} />
      )}
    </label>
  )
}

export function Puce({ ton, children }: { ton?: 'bon' | 'mauvais'; children: ReactNode }) {
  return <span className={`puce ${ton ?? ''}`}>{children}</span>
}
