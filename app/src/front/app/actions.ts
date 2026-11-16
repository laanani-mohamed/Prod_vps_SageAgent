'use server'

import { cookies, headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { API_URL, cookiesSession, estHttps, lireJeton } from '../lib/session'

export type ErreurConnexion = { titre: string; message: string; username: string } | null

export async function connexion(_: ErreurConnexion, form: FormData): Promise<ErreurConnexion> {
  const username = String(form.get('username') ?? '').trim()
  const password = String(form.get('password') ?? '')
  const erreur = (titre: string, message: string) => ({ titre, message, username })
  if (!username || !password) return erreur('Champs manquants', 'Veuillez saisir vos identifiants.')

  const h = await headers()
  const ip = h.get('x-forwarded-for')
  let r: Response
  try {
    r = await fetch(`${API_URL}/api/auth/token`, {
      method: 'POST',
      body: new URLSearchParams({ username, password }),
      headers: ip ? { 'X-Forwarded-For': ip } : {}, // limite de l'API (5 essais / min) par poste, pas pour tout le serveur
    })
  } catch {
    return erreur('Serveur injoignable', 'Impossible de joindre le serveur API. Réessayez dans un instant.')
  }
  if (r.status === 429) return erreur('Trop de tentatives', 'Patientez une minute avant de réessayer.')
  if (!r.ok) return erreur('Connexion refusée', (await r.json().catch(() => null))?.detail ?? 'Erreur du serveur API.')

  const { access_token, refresh_token } = await r.json()
  if (!lireJeton(access_token).client) return erreur('Connexion refusée', "Aucun client n'est associé à ce compte.")
  const jar = await cookies()
  cookiesSession(access_token, refresh_token, estHttps(h)).forEach(([nom, valeur, options]) => jar.set(nom, valeur, options))
  redirect('/')
}

export async function deconnexion() {
  const jar = await cookies()
  const access = jar.get('access')?.value
  const refresh = jar.get('refresh')?.value
  if (access && refresh) {
    // Révoque les jetons côté API ; les cookies sont supprimés même si l'API ne répond pas
    await fetch(`${API_URL}/api/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${access}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    }).catch(() => {})
  }
  jar.delete('access')
  jar.delete('refresh')
  redirect('/login')
}
