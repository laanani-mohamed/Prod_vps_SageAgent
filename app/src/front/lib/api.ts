import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { API_URL, lireJeton } from './session'

/** Session de la requête (jeton présent et valide : vérifié par proxy.ts). */
export async function session() {
  return lireJeton((await cookies()).get('access')!.value)
}

export const estCollaborateur = (s: { roles: string[] }) => s.roles.includes('collaborateur')

/** Appel de l'API côté serveur avec le jeton de la session. 401 → reconnexion ; 403 → null (section interdite). */
export async function api<T = any>(chemin: string, corps?: object): Promise<T | null> {
  const r = await fetch(API_URL + chemin, {
    method: corps ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${(await cookies()).get('access')?.value}`, 'Content-Type': 'application/json' },
    body: corps ? JSON.stringify(corps) : undefined,
    cache: 'no-store',
  })
  if (r.status === 401) redirect('/login')
  if (r.status === 403) return null
  if (!r.ok) throw new Error(`${chemin} : ${r.status}`)
  return r.json()
}

/** Vue de api/bi/vues.py pour le client de la session ; `coNo` : filtre commercial du directeur. */
export async function vue<T = any>(nom: string, filtres: object = {}, coNo: number[] = []) {
  return api<T>(`/api/bi/vues/${nom}`, { client_schema: (await session()).client, filtres, co_no: coNo })
}
