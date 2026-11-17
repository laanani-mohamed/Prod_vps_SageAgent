'use client'

// Plan des dépôts : parc de bâtiments (hauteur = valeur du stock) → plan isométrique d'un dépôt,
// une pièce par famille (étagères remplies selon la quantité) → articles de la famille choisie.
import { useState } from 'react'
import { court, entier, mad } from '../lib/format'
import { Kpis } from './ui'

type Article = { ar_ref: string; ar_design: string; qte_stock: number; valeur_stock: number }
type Famille = { code: string; nom: string | null; valeur: number; quantite: number; articles: number; top: Article[] }
export type Depot = { no: number; nom: string | null; valeur: number; quantite: number; articles: number; nb_familles: number; familles: Famille[] }

const iso = (gx: number, gy: number, h = 0) => [504 + 36 * (gx - gy), 70 + 18 * (gx + gy) - h]
const pts = (...p: number[][]) => p.map((x) => x.join(',')).join(' ')
const statut = (q: number) => (q >= 500 ? '#16a34a' : q >= 100 ? '#d97706' : '#dc2626')

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

function Piece({ f, j, max, choisie, ouvrir }: { f: Famille; j: number; max: number; choisie: boolean; ouvrir: () => void }) {
  const gx = 1 + 5 * (j % 3), gy = 1 + 5 * Math.floor(j / 3)
  const [T, R, B, L] = [iso(gx, gy), iso(gx + 4, gy), iso(gx + 4, gy + 4), iso(gx, gy + 4)]
  const haut = (q: number[], h: number) => [q[0], q[1] - h]
  const niveaux = Math.max(1, Math.ceil((f.quantite / max) * 18))
  const etageres = [0, 1, 2, 3, 4, 5].map((k) => {
    const n = Math.max(0, Math.min(3, niveaux - 3 * k))
    const x = gx + 0.55 + (k % 3) * 1.15, y = gy + 0.7 + Math.floor(k / 3) * 1.5, h = n ? n * 13 : 2
    const b = [iso(x, y), iso(x + 0.75, y), iso(x + 0.75, y + 0.45), iso(x, y + 0.45)]
    return { n, dessus: pts(...b.map((q) => haut(q, h))), gauche: pts(b[3], b[2], haut(b[2], h), haut(b[3], h)), droite: pts(b[1], b[2], haut(b[2], h), haut(b[1], h)) }
  })
  return (
    <g>
      <polygon className={`piece-sol${choisie ? ' choisie' : ''}`} points={pts(T, R, B, L)} fill="#ffffff" stroke="var(--bord)" strokeWidth="1.5" onClick={ouvrir} />
      <polygon points={pts(L, T, haut(T, 46), haut(L, 46))} fill="#ffffff" stroke="var(--bord)" />
      <polygon points={pts(T, R, haut(R, 46), haut(T, 46))} fill="var(--gris)" stroke="var(--bord)" />
      <polygon points={pts(R, B, haut(B, 14), haut(R, 14))} fill="var(--gris)" stroke="var(--bord)" />
      {etageres.map((e, k) => (
        <g key={k} opacity={e.n ? 1 : 0.35}>
          <polygon points={e.droite} fill="var(--accent-fonce)" />
          <polygon points={e.gauche} fill="var(--accent)" />
          <polygon points={e.dessus} fill={e.n ? 'color-mix(in srgb, var(--accent) 45%, #fff)' : 'var(--bord)'} />
        </g>
      ))}
    </g>
  )
}

function Etiquette({ f, j, ouvrir }: { f: Famille; j: number; ouvrir: () => void }) {
  const [cx, cy] = iso(3 + 5 * (j % 3), 3 + 5 * Math.floor(j / 3))
  const x = cx - 98, y = cy - 128
  return (
    <g className="etiquette-plan" role="button" tabIndex={0} aria-label={`Ouvrir la section ${f.nom ?? f.code} : ${entier(f.quantite)} unités`}
      onClick={ouvrir} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), ouvrir())}>
      <rect x={x} y={y} width="196" height="50" rx="12" fill="#ffffff" stroke="var(--bord)" />
      <text x={x + 14} y={y + 21} fontSize="13" fontWeight="700" fill="var(--texte)">{(f.nom ?? f.code).trim().slice(0, 22)}</text>
      <text x={x + 14} y={y + 39} fontSize="12" fill="var(--doux)">{entier(f.quantite)} u · {court(f.valeur)}</text>
      <circle cx={x + 180} cy={y + 35} r="5" fill={statut(f.quantite)} />
    </g>
  )
}

type Totaux = { depots: number; valeur: number; articles: number; quantite: number }

export default function PlanDepots({ depots, totaux }: { depots: Depot[]; totaux: Totaux }) {
  const [i, setI] = useState<number | null>(null)
  const [j, setJ] = useState<number | null>(null)
  const max = Math.max(...depots.map((d) => d.valeur), 1)
  const d = i === null ? null : depots[i]
  const f = d && j !== null ? d.familles[j] : null

  const kpis = (
    <Kpis items={d ? [
      { nom: 'Dépôt', v: `${d.nom ?? ''} (${d.no})` }, { nom: 'Valeur du stock', v: court(d.valeur), sous: `${mad(d.valeur)} MAD` },
      { nom: 'Articles en stock', v: entier(d.articles) }, { nom: 'Unités en stock', v: entier(d.quantite) },
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
            <button key={x.no} type="button" className="batiment" onClick={() => setI(k)} aria-label={`Voir le plan du dépôt ${x.nom ?? x.no}`}>
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

  const maxQ = Math.max(...d.familles.map((x) => x.quantite), 1)
  return (<>
    {kpis}
    <section className="carte">
      <div className="carte-titre">
        <nav className="fil" aria-label="Fil d'Ariane">
          <button type="button" onClick={() => { setI(null); setJ(null) }}>Dépôts</button>›
          <button type="button" onClick={() => setJ(null)}>{d.nom ?? `Dépôt ${d.no}`}</button>
          {f && <>› <span>{f.nom ?? f.code}</span></>}
        </nav>
        <span className="doux petit">{entier(d.nb_familles)} familles · les {d.familles.length} plus stockées · ● ≥ 500 · ● 100 à 499 · ● &lt; 100 unités</span>
      </div>
      <div className={f ? 'plan' : 'plan sans-panneau'}>
        <svg viewBox="0 -40 1080 680" role="group" aria-label={`Plan du dépôt ${d.nom ?? d.no}`}>
          <polygon points="504,70 1080,358 576,610 0,322" fill="var(--fond)" stroke="var(--bord)" strokeWidth="2" />
          <polygon points="0,322 504,70 504,40 0,292" fill="#ffffff" stroke="var(--bord)" />
          <polygon points="504,70 1080,358 1080,328 504,40" fill="var(--gris)" stroke="var(--bord)" />
          <polyline className="allee" points="666,187 306,367" fill="none" stroke="var(--accent)" strokeWidth="3" opacity="0.45" />
          <polyline className="allee" points="342,187 846,439" fill="none" stroke="var(--accent)" strokeWidth="3" opacity="0.45" />
          {d.familles.map((x, k) => <Piece key={x.code ?? k} f={x} j={k} max={maxQ} choisie={k === j} ouvrir={() => setJ(k)} />)}
          {d.familles.map((x, k) => <Etiquette key={`e-${x.code ?? k}`} f={x} j={k} ouvrir={() => setJ(k)} />)}
        </svg>
        {f && (
          <aside className="carte" aria-label={`Articles de la section ${f.nom ?? f.code}`}>
            <div className="carte-titre"><h2>{f.nom ?? f.code}</h2><button type="button" className="secondaire" onClick={() => setJ(null)}>Fermer</button></div>
            <p className="doux petit">Section {f.code} · {entier(f.quantite)} unités · {court(f.valeur)} · {entier(f.articles)} articles</p>
            <table className="tableau">
              <thead><tr><th>Réf.</th><th>Désignation</th><th className="droite">Qté</th><th className="droite">Valeur</th></tr></thead>
              <tbody>
                {f.top.map((a) => (
                  <tr key={a.ar_ref}><td>{a.ar_ref}</td><td title={a.ar_design}>{a.ar_design}</td><td className="droite">{entier(a.qte_stock)}</td><td className="droite">{court(a.valeur_stock)}</td></tr>
                ))}
              </tbody>
            </table>
          </aside>
        )}
      </div>
    </section>
  </>)
}
