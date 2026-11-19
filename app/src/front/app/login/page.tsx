'use client'

import { useActionState, useState } from 'react'
import { connexion } from '../actions'

const ICONES = {
  utilisateur: 'M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21a8 8 0 0 1 16 0',
  cadenas: 'M4 10h16v11H4zM8 10V7a4 4 0 0 1 8 0v3',
  oeil: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  masquer: 'M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.1A9.8 9.8 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.6 6.6C3.9 8.4 2 12 2 12s4 7 10 7a9.6 9.6 0 0 0 5.4-1.6',
}
// Dégradé du noir au gris des motifs de fond (maquette « Connexion — motifs statistiques »)
const GRIS = ['#18181b', '#27272a', '#3f3f46', '#52525b', '#626269', '#71717a', '#8b8b94', '#a1a1aa', '#b4b4bc']
const BARRES = [70, 110, 90, 140, 120, 165, 130, 180, 150]
const POINTS: [number, number, number, number][] = [   // x, y, rayon, nuance
  [56, 196, 6, 0], [74, 176, 4, 7], [92, 190, 8, 1], [110, 160, 5, 2], [128, 172, 4, 0], [146, 142, 9, 5], [164, 150, 5, 1],
  [182, 124, 6, 3], [200, 138, 4, 7], [218, 110, 7, 0], [236, 118, 4, 8], [254, 96, 10, 4], [272, 104, 5, 2], [290, 80, 6, 1],
  [308, 88, 4, 5], [326, 64, 7, 7],
]
const LIGNES_TABLEAU: [number, number][] = [[0, 86], [1, 68], [2, 52], [7, 37], [3, 24]]   // nuance, % de la barre

function Icone({ d }: { d: string }) {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d={d} />
    </svg>
  )
}

/** Motifs de statistiques en fond (décor seulement : histogramme, anneau, courbe, nuage de points, tableau). */
function Motifs() {
  const plus = <svg width="18" height="18" viewBox="0 0 18 18"><path d="M9 2v14M2 9h14" stroke="#a1a1aa" strokeWidth="1.5" /></svg>
  return (
    <div aria-hidden="true">
      <div className="points" />
      <svg className="motif m-histo m-cote" width="400" height="230" viewBox="0 0 400 230">
        <g stroke="#d4d4d8" strokeDasharray="3 6">{[40, 93, 146].map((y) => <line key={y} x1="16" y1={y} x2="392" y2={y} />)}</g>
        <line x1="16" y1="200" x2="392" y2="200" stroke="#a1a1aa" strokeWidth="1.5" />
        {BARRES.map((h, i) => (
          <rect key={i} className="pousse" x={28 + i * 40} y={200 - h} width="28" height={h} rx="5" fill={GRIS[i]} style={{ animationDelay: `${0.05 * (i + 1)}s` }} />
        ))}
        <polyline points={BARRES.map((h, i) => `${42 + i * 40},${186 - h}`).join(' ')} fill="none" stroke="#71717a" strokeWidth="1.5" strokeDasharray="4 4" />
      </svg>
      <svg className="motif m-anneau" width="240" height="240" viewBox="0 0 240 240">
        <circle className="lent" cx="120" cy="120" r="104" fill="none" stroke="#d4d4d8" strokeWidth="1.5" strokeDasharray="2 7" />
        <g transform="rotate(-90 120 120)" fill="none" strokeWidth="24">
          {[[131.7, 0], [95.5, -135.7], [77.4, -235.2], [68.4, -316.6], [59.3, -389]].map(([l, o], i) => (
            <circle key={i} cx="120" cy="120" r="72" stroke={GRIS[i * 2]} strokeDasharray={`${l} 452.4`} strokeDashoffset={o} />
          ))}
        </g>
        <circle cx="120" cy="120" r="44" fill="none" stroke="#e4e4e7" strokeWidth="1.5" />
        <circle cx="120" cy="120" r="5" fill="#a1a1aa" />
      </svg>
      <svg className="motif m-courbe" width="220" height="56" viewBox="0 0 220 56">
        <polyline points="4,44 28,38 52,42 76,26 100,30 124,18 148,24 172,10 196,16" fill="none" stroke="#27272a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="196" cy="16" r="4.5" fill="#27272a" />
        <line x1="4" y1="52" x2="216" y2="52" stroke="#d4d4d8" />
      </svg>
      <svg className="motif m-nuage m-cote" width="360" height="250" viewBox="0 0 360 250">
        <path d="M30 20v202h320" fill="none" stroke="#a1a1aa" strokeWidth="1.5" />
        <g stroke="#d4d4d8" strokeDasharray="3 6">{[70, 120, 170].map((y) => <line key={y} x1="30" y1={y} x2="350" y2={y} />)}</g>
        <line x1="44" y1="204" x2="340" y2="56" stroke="#52525b" strokeWidth="2" strokeDasharray="6 5" />
        {POINTS.map(([x, y, r, n], i) => <circle key={i} cx={x} cy={y} r={r} fill={GRIS[n]} />)}
      </svg>
      <div className="motif m-tableau m-cote">
        <div className="rang entete"><span /><i /><i style={{ width: '60%' }} /><i /></div>
        {LIGNES_TABLEAU.map(([n, w]) => (
          <div key={n} className="rang">
            <span style={{ background: GRIS[n] }} /><i /><i className="piste-motif"><b style={{ width: `${w}%`, background: GRIS[n] }} /></i><i />
          </div>
        ))}
        <div className="empile">
          {[[46, 22, 18, 14, 100], [30, 34, 20, 16, 78]].map(([a, b, c, d, w], i) => (
            <div key={i} style={{ width: `${w}%` }}>
              {[a, b, c, d].map((p, j) => <span key={j} style={{ width: `${p}%`, background: [GRIS[7], GRIS[3], GRIS[0], GRIS[5]][j] }} />)}
            </div>
          ))}
        </div>
      </div>
      <span className="motif m-plus" style={{ left: '35%', top: '14%' }}>{plus}</span>
      <span className="motif m-plus" style={{ left: '66%', top: '33%' }}>{plus}</span>
      <span className="motif m-plus" style={{ left: '33%', top: '62%' }}>{plus}</span>
      <span className="motif m-plus" style={{ left: '69%', top: '13%' }}>{plus}</span>
    </div>
  )
}

export default function PageConnexion() {
  const [erreur, action, enCours] = useActionState(connexion, null)
  const [voir, setVoir] = useState(false)

  return (
    <div className="connexion">
      <Motifs />
      <main className="formulaire">
        <div className="marque">
          <span className="logo">IT</span>BORD
        </div>
        <div className="carte">
          <h1>Se connecter à votre compte</h1>
          <p className="aide">Saisissez les identifiants fournis par votre administrateur.</p>
          {erreur && (
            <div role="alert" className="alerte">
              <strong>{erreur.titre}</strong>
              {erreur.message}
            </div>
          )}
          <form action={action}>
            <label htmlFor="username">Nom d&apos;utilisateur</label>
            <div className="champ">
              <Icone d={ICONES.utilisateur} />
              <input id="username" name="username" autoComplete="username" placeholder="ex : prenom.nom"
                defaultValue={erreur?.username} aria-invalid={!!erreur} required />
            </div>
            <label htmlFor="password">Mot de passe</label>
            <div className="champ">
              <Icone d={ICONES.cadenas} />
              <input id="password" name="password" type={voir ? 'text' : 'password'} autoComplete="current-password"
                placeholder="••••••••" aria-invalid={!!erreur} required />
              <button type="button" className="oeil" onClick={() => setVoir(!voir)} aria-pressed={voir}
                aria-label={voir ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}>
                <Icone d={voir ? ICONES.masquer : ICONES.oeil} />
              </button>
            </div>
            <button type="submit" className="principal" disabled={enCours}>
              {enCours && <span className="cercle" aria-hidden="true" />}
              {enCours ? 'Connexion…' : 'Se connecter'}
            </button>
          </form>
        </div>
        <p className="pied">
          <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={ICONES.cadenas} /></svg>
          Connexion sécurisée — Plateforme Business Intelligence Sage
        </p>
      </main>
    </div>
  )
}
