// Session : les deux jetons de l'API dans des cookies httpOnly, jamais lisibles par le JavaScript de la page.
export const API_URL = process.env.API_URL ?? 'http://127.0.0.1:8000'

export type Session = { username: string; roles: string[]; coNo: number | null; client: string | null; exp: number }

/** Contenu du jeton, pour l'affichage seulement : l'API vérifie sa signature à chaque appel. */
export function lireJeton(jeton: string): Session {
  const p = JSON.parse(Buffer.from(jeton.split('.')[1], 'base64url').toString())
  return { username: p.sub, roles: p.roles ?? [], coNo: p.co_no ?? null, client: p.schemas?.[0] ?? null, exp: p.exp ?? 0 }
}

/** Jeton présent, lisible et encore valable au moins 30 secondes. */
export function valide(jeton?: string): jeton is string {
  try {
    return !!jeton && lireJeton(jeton).exp * 1000 > Date.now() + 30_000
  } catch {
    return false
  }
}

/** Requête arrivée en HTTPS derrière un proxy : les cookies sont alors marqués Secure. */
export const estHttps = (h: { get(nom: string): string | null }) => h.get('x-forwarded-proto')?.split(',')[0] === 'https'

/** Cookies à poser après une connexion ou un renouvellement ; chacun expire avec son jeton. */
export function cookiesSession(access: string, refresh: string, https: boolean) {
  return ([['access', access], ['refresh', refresh]] as const).map(([nom, jeton]) => [
    nom,
    jeton,
    { httpOnly: true, sameSite: 'lax', secure: https, path: '/', expires: new Date(lireJeton(jeton).exp * 1000) },
  ] as const)
}
