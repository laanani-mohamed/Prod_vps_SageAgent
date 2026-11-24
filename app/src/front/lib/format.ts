// Formats d'affichage (fr-FR). null / undefined → « N/A » (donnée non renvoyée pour le profil).
const nf = (d: number) => new Intl.NumberFormat('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
const N0 = nf(0), N1 = nf(1), N2 = nf(2)
const absent = (v: unknown): v is null | undefined => v === null || v === undefined

export const mad = (v?: number | null) => (absent(v) ? 'N/A' : N2.format(v))
export const entier = (v?: number | null) => (absent(v) ? 'N/A' : N0.format(v))
export const pct = (v?: number | null, signe = false) =>
  absent(v) ? 'N/A' : `${signe && v > 0 ? '+' : ''}${N1.format(v)} %`

/** Montant adapté à sa grandeur : [nombre, unité] — MMAD dès 1 million, KMAD dès 1 000, sinon MAD
 *  (jamais « 0,25 MMAD » ni « 0,4 KMAD »). */
export function montant(v?: number | null): [string, string] {
  if (absent(v)) return ['N/A', '']
  const a = Math.abs(v)
  return a >= 1e6 ? [N2.format(v / 1e6), 'MMAD'] : a >= 1e3 ? [N1.format(v / 1e3), 'KMAD'] : [N2.format(v), 'MAD']
}

/** Montant abrégé : 5,20 MMAD · 354,2 KMAD · 980,00 MAD. */
export function court(v?: number | null) {
  const [n, u] = montant(v)
  return u ? `${n} ${u}` : n
}

/** Année (ou années) d'une période : « 2025 », ou « 2024-2025 » si elle chevauche deux années. */
export const annees = (du: string, au: string) => (du.slice(0, 4) === au.slice(0, 4) ? du.slice(0, 4) : `${du.slice(0, 4)}-${au.slice(0, 4)}`)

/** Même date décalée de `n` années (29 février → 28 février). */
export function decaler(iso: string, n: number) {
  const a = Number(iso.slice(0, 4)) - n
  const md = iso.slice(5, 10) === '02-29' ? '02-28' : iso.slice(5, 10)
  return `${a}-${md}`
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

/** Horodatage ISO → 'JJ/MM/AAAA HH:MM', à l'heure enregistrée par l'ETL (comme Streamlit et les rapports PDF). */
export const dateHeure = (iso?: string | null) => (iso
  ? new Date(iso).toLocaleString('fr-FR', { timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  : '-')

/** Options d'une liste déroulante de commerciaux (réponse de /api/referentiel/collaborateurs). */
export const optionsCommerciaux = (rep: { data?: any[] } | null): [string, string][] =>
  [['', 'Tous'], ...(rep?.data ?? []).map((c): [string, string] => [String(c.co_no), nomCommercial(c)])]
