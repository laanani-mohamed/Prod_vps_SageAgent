'use client'

import { useActionState, useState } from 'react'
import { connexion } from '../actions'

const ICONES = {
  utilisateur: 'M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21a8 8 0 0 1 16 0',
  cadenas: 'M4 10h16v11H4zM8 10V7a4 4 0 0 1 8 0v3',
  oeil: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  masquer: 'M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.1A9.8 9.8 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.6 6.6C3.9 8.4 2 12 2 12s4 7 10 7a9.6 9.6 0 0 0 5.4-1.6',
}
function Icone({ d }: { d: string }) {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d={d} />
    </svg>
  )
}

export default function PageConnexion() {
  const [erreur, action, enCours] = useActionState(connexion, null)
  const [voir, setVoir] = useState(false)

  return (
    <div className="connexion">
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
