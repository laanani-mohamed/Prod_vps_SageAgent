// Filtres et sélection des pages : dans l'URL (formulaires GET, liens), donc partageables et sans état côté client.
export type Params = Record<string, string | string[] | undefined>

/** Valeur texte d'un paramètre ('' si absent). */
export const lire = (p: Params, cle: string) => (typeof p[cle] === 'string' ? (p[cle] as string) : '')

/** Lien vers `chemin` avec les paramètres actuels modifiés (undefined / '' = retiré). */
export function lien(chemin: string, p: Params, changements: Record<string, string | number | undefined> = {}) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries({ ...p, ...changements })) {
    if (typeof v === 'string' ? v !== '' : typeof v === 'number') q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `${chemin}?${s}` : chemin
}

/** 1er janvier de l'année en cours et aujourd'hui (AAAA-MM-JJ) : période par défaut. */
export function anneeEnCours() {
  const auj = new Date().toISOString().slice(0, 10)
  return { debut: `${auj.slice(0, 4)}-01-01`, fin: auj }
}
