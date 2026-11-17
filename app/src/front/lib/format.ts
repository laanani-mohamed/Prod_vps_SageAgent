// Formats d'affichage (fr-FR). null / undefined → « N/A » (donnée non renvoyée pour le profil).
const nf = (d: number) => new Intl.NumberFormat('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
const N0 = nf(0), N1 = nf(1), N2 = nf(2)
const absent = (v: unknown): v is null | undefined => v === null || v === undefined

export const mad = (v?: number | null) => (absent(v) ? 'N/A' : N2.format(v))
export const entier = (v?: number | null) => (absent(v) ? 'N/A' : N0.format(v))
export const pct = (v?: number | null, signe = false) =>
  absent(v) ? 'N/A' : `${signe && v > 0 ? '+' : ''}${N1.format(v)} %`

/** Montant abrégé : 5,20 MMAD · 354,2 KMAD · 980,00 DH. */
export function court(v?: number | null) {
  if (absent(v)) return 'N/A'
  const a = Math.abs(v)
  return a >= 1e6 ? `${N2.format(v / 1e6)} MMAD` : a >= 1e3 ? `${N1.format(v / 1e3)} KMAD` : `${N2.format(v)} DH`
}

/** 2026-11-02(T…) → 02/11/2026. */
export const date = (iso?: string | null) => (iso ? iso.slice(0, 10).split('-').reverse().join('/') : '—')

/** Cellule de tableau : nombre entier ou décimal formaté, texte tel quel. */
export const cellule = (v: unknown) =>
  typeof v === 'number' ? (Number.isInteger(v) ? N0.format(v) : N2.format(v)) : absent(v) || v === '' ? '—' : String(v)

/** Texte lisible sur une couleur (#rrggbb) : noir sur couleur claire, blanc sur couleur foncée. */
export function surCouleur(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.18 ? '#09090b' : '#ffffff'
}

/** Commercial (F_DOCENTETE.co_no) : 0 → « Non identifié », sinon « nom prénom ». */
export const nomCommercial = (c: { co_no: number; co_nom?: string | null; co_prenom?: string | null }) =>
  c.co_no === 0 ? 'Non identifié' : [c.co_nom, c.co_prenom].filter(Boolean).join(' ') || `Commercial ${c.co_no}`

/** Options d'une liste déroulante de commerciaux (réponse de /api/referentiel/collaborateurs). */
export const optionsCommerciaux = (rep: { data?: any[] } | null): [string, string][] =>
  [['', 'Tous'], ...(rep?.data ?? []).map((c): [string, string] => [String(c.co_no), nomCommercial(c)])]
