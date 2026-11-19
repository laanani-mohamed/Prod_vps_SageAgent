'use client'

// Plan des dépôts : parc de bâtiments (hauteur = valeur du stock) → détail d'un dépôt : familles en surfaces
// proportionnelles à leur valeur (palette du rapport 9) → rayonnage de la famille choisie (articles les plus stockés).
import { useState } from 'react'
import { court, entier, mad, pct } from '../lib/format'
import { Kpis } from './ui'

type Article = { ar_ref: string; ar_design: string; qte_stock: number; valeur_stock: number }
type Famille = { code: string; nom: string | null; valeur: number; quantite: number; articles: number; top: Article[] }
export type Depot = { no: number; nom: string | null; valeur: number; quantite: number; articles: number; nb_familles: number; familles: Famille[] }

const pts = (...p: number[][]) => p.map((x) => x.join(',')).join(' ')
// Familles du dépôt : couleurs du rapport 9 (Balance Âgée) + une nuance ; texte blanc sur les deux plus foncées
const TUILES = [['#1d3354', '#ffffff'], ['#467599', '#ffffff'], ['#d64045', '#1c1410'], ['#9ed8db', '#1c1410'], ['#e9fff9', '#1c1410'], ['#8fb0c8', '#1c1410']]
const ASPECT = 2.8   // largeur / hauteur de la carte des familles

type Tuile = { k: number; nom: string; v: number; poids: number; x: number; y: number; w: number; h: number }

/** Rectangles proportionnels : partage récursif en deux groupes de poids voisins, dans le sens le plus long (en %). */
function decouper(items: Omit<Tuile, 'x' | 'y' | 'w' | 'h'>[], x: number, y: number, w: number, h: number, out: Tuile[]) {
  if (items.length === 1) { out.push({ ...items[0], x, y, w, h }); return }
  const total = items.reduce((s, i) => s + i.poids, 0)
  let acc = 0, k = 0
  while (k < items.length - 1 && acc + items[k].poids <= total / 2) { acc += items[k].poids; k++ }
  if (k === 0) { acc = items[0].poids; k = 1 }
  const r = acc / total
  if (w * ASPECT >= h) { decouper(items.slice(0, k), x, y, w * r, h, out); decouper(items.slice(k), x + w * r, y, w * (1 - r), h, out) }
  else { decouper(items.slice(0, k), x, y, w, h * r, out); decouper(items.slice(k), x, y + h * r, w, h * (1 - r), out) }
}

function Batiment({ d, max }: { d: Depot; max: number }) {
  const h = 22 + 118 * Math.sqrt(Math.max(d.valeur, 0) / max)
  const t = (x: number, y: number) => [x, y - h]
  return (
    <svg viewBox="0 0 240 215" aria-hidden="true">
      <ellipse cx="120" cy="200" rx="88" ry="16" fill="#09090b" opacity="0.07" />
      <polygon points="50,165 120,200 190,165 120,130" fill="var(--gris)" />
      <polygon points={pts([50, 165], [120, 200], t(120, 200), t(50, 165))} fill="var(--accent-fonce)" />
      <polygon points={pts([120, 200], [190, 165], t(190, 165), t(120, 200))} fill="var(--accent)" />
      <polygon points={pts(t(50, 165), t(120, 200), t(190, 165), t(120, 130))} fill="color-mix(in srgb, var(--accent) 45%, #fff)" />
      <polygon points={pts([140, 190], [168, 176], [168, 176 - Math.min(h - 4, 30)], [140, 190 - Math.min(h - 4, 30)])} fill="#09090b" opacity="0.5" />
    </svg>
  )
}

type Totaux = { depots: number; valeur: number; articles: number; quantite: number }

export default function PlanDepots({ depots, totaux }: { depots: Depot[]; totaux: Totaux }) {
  const [i, setI] = useState<number | null>(null)
  const [j, setJ] = useState(0)
  const max = Math.max(...depots.map((d) => d.valeur), 1)
  const d = i === null ? null : depots[i]
  const kpis = (
    <Kpis items={d ? [
      { nom: 'Valeur du stock', v: court(d.valeur), sous: `${pct(totaux.valeur ? d.valeur / totaux.valeur * 100 : 0)} de la valeur de tous les dépôts` },
      { nom: 'Unités en stock', v: entier(d.quantite) }, { nom: 'Articles en stock', v: entier(d.articles) }, { nom: 'Familles présentes', v: entier(d.nb_familles) },
    ] : [
      { nom: 'Dépôts', v: entier(totaux.depots) }, { nom: 'Valeur du stock', v: court(totaux.valeur), sous: `${mad(totaux.valeur)} MAD` },
      { nom: 'Articles en stock', v: entier(totaux.articles) }, { nom: 'Unités en stock', v: entier(totaux.quantite) },
    ]} />
  )

  if (!d) {
    return (<>
      {kpis}
      <section className="carte">
        <div className="carte-titre"><h2>Choisissez un dépôt</h2><span className="doux">hauteur du bâtiment = valeur du stock</span></div>
        <div className="parc">
          {depots.map((x, k) => (
            <button key={x.no} type="button" className="batiment" onClick={() => { setI(k); setJ(0) }} aria-label={`Voir le plan du dépôt ${x.nom ?? x.no}`}>
              <Batiment d={x} max={max} />
              <span>
                <span className="petit doux">Dépôt {x.no}</span>
                <strong>{x.nom ?? `Dépôt ${x.no}`}</strong>
                <strong className="grand-moyen">{court(x.valeur)}</strong>
                <span className="petit doux">{entier(x.articles)} article(s) · {entier(x.quantite)} unités</span>
              </span>
            </button>
          ))}
        </div>
      </section>
    </>)
  }

  // Surface = valeur du stock (unités pour un dépôt non valorisé) ; les familles non détaillées sont regroupées.
  const parValeur = d.valeur > 0
  const poids = (v: number, q: number) => Math.max(parValeur ? v : q, 1e-6)
  const items = d.familles.map((x, k) => ({ k, nom: `${x.code} · ${(x.nom ?? x.code).trim()}`, v: parValeur ? x.valeur : x.quantite, poids: poids(x.valeur, x.quantite) }))
  const reste = {
    k: -1, nom: `${entier(d.nb_familles - d.familles.length)} autres familles`,
    v: (parValeur ? d.valeur : d.quantite) - items.reduce((s, x) => s + x.v, 0), poids: 0,
  }
  reste.poids = Math.max(reste.v, 0)
  const tuiles: Tuile[] = []
  if (items.length) decouper(d.nb_familles > d.familles.length && reste.poids > 0 ? [...items, reste] : items, 0, 0, 100, 100, tuiles)
  const base = parValeur ? d.valeur : d.quantite
  const f = d.familles[j] ?? d.familles[0]
  const maxQ = Math.max(...(f?.top ?? []).map((a) => a.qte_stock), 1)

  return (<>
    <div className="choix-depots">
      <button type="button" className="secondaire" onClick={() => setI(null)}>‹ Tous les dépôts</button>
      {depots.map((x, k) => (
        <button key={x.no} type="button" className={k === i ? 'pastille-depot actif' : 'pastille-depot'} aria-pressed={k === i} onClick={() => { setI(k); setJ(0) }}>
          {x.nom ?? `Dépôt ${x.no}`}<span>{court(x.valeur)}</span>
        </button>
      ))}
    </div>
    {kpis}
    <section className="carte">
      <div className="carte-titre">
        <h2>Familles du dépôt {d.nom ?? d.no}</h2>
        <span className="doux">{parValeur ? 'surface = valeur du stock · cliquez une famille' : 'stock non valorisé : surface = unités'}</span>
      </div>
      {!tuiles.length ? <p className="vide">Aucun article en stock dans ce dépôt.</p> : (
        <div className="carte-familles">
          {tuiles.map((t) => {
            const autres = t.k < 0, [fond, texte] = autres ? ['#ece7e2', '#3f3f46'] : TUILES[Math.min(t.k, TUILES.length - 1)]
            const style = { left: `${t.x}%`, top: `${t.y}%`, width: `${t.w}%`, height: `${t.h}%`, background: fond, color: texte }
            const contenu = <>
              <span className="nom">{t.nom}</span>
              {t.w * t.h > 140 && <span><strong>{parValeur ? court(t.v) : `${entier(t.v)} u.`}</strong><span>{pct(base ? t.v / base * 100 : 0)} du dépôt</span></span>}
            </>
            return autres
              ? <div key="autres" className="tuile autres" style={style} title={`${t.nom} (non détaillées)`}>{contenu}</div>
              : <button key={t.k} type="button" className={t.k === j ? 'tuile choisie' : 'tuile'} style={style} aria-pressed={t.k === j} onClick={() => setJ(t.k)}>{contenu}</button>
          })}
        </div>
      )}
    </section>
    {f && (
      <section className="carte rayonnage" aria-label={`Rayonnage de la famille ${f.nom ?? f.code}`}>
        <div className="carte-titre">
          <div><div className="sur-titre">Rayonnage · {f.code}</div><h2>{(f.nom ?? f.code).trim()}</h2></div>
          <span className="pastille">{pct(d.valeur ? f.valeur / d.valeur * 100 : 0)} de la valeur du dépôt</span>
        </div>
        <div className="chiffres-famille">
          <div><span className="doux petit">Valeur</span><strong>{court(f.valeur)}</strong></div>
          <div><span className="doux petit">Unités</span><strong>{entier(f.quantite)}</strong></div>
          <div><span className="doux petit">Articles</span><strong>{entier(f.articles)}</strong></div>
        </div>
        <h3>Les plus stockés de la famille</h3>
        <ol className="etageres">
          {f.top.map((a, k) => (
            <li key={a.ar_ref}>
              <span className="rang">{k + 1}</span>
              <span className="article">
                <span className="coupe" title={a.ar_design}><strong>{a.ar_ref}</strong> · {a.ar_design}</span>
                <span className="piste"><span style={{ width: `${(a.qte_stock / maxQ) * 100}%` }} /></span>
              </span>
              <span className="droite"><strong>{entier(a.qte_stock)} u.</strong><span className="doux petit">{court(a.valeur_stock)}</span></span>
            </li>
          ))}
        </ol>
        <p className="doux petit">{f.top.length} articles les plus stockés sur {entier(f.articles)} dans cette famille.</p>
      </section>
    )}
  </>)
}
