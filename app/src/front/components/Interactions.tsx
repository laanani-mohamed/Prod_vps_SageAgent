'use client'

// Retour visuel pendant un chargement : l'élément cliqué se verrouille et affiche un cercle qui tourne,
// pour montrer que le traitement est en cours et éviter d'envoyer la même requête plusieurs fois.
import { useLinkStatus } from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useRef, useState, useTransition, type ComponentProps, type FormEvent, type MouseEvent, type ReactNode } from 'react'

/** À placer dans un <Link> : cercle pendant la navigation (le lien est alors verrouillé, voir globals.css). */
export function Attente() {
  const { pending } = useLinkStatus()
  return pending ? <span className="cercle" role="status" aria-label="Chargement en cours" /> : null
}

/** Corps d'un tableau dont chaque ligne a un lien dans sa 1re cellule : un clic n'importe où sur la ligne suit
 *  ce lien. Fait en JavaScript plutôt qu'avec un lien étendu par CSS (position: relative sur <tr>), ignoré par
 *  certains navigateurs : le clic partait alors toujours vers la dernière ligne. Rien pendant un chargement. */
export function CorpsCliquable({ children }: { children: ReactNode }) {
  function clic(e: MouseEvent<HTMLTableSectionElement>) {
    const cible = e.target as HTMLElement
    if (cible.closest('a') || e.currentTarget.querySelector('.cercle')) return
    cible.closest('tr')?.querySelector('a')?.click()
  }
  return <tbody onClick={clic}>{children}</tbody>
}

/** Formulaire GET de filtres : navigation rapide vers la page courante avec les champs dans l'URL.
 *  Tant que la page n'est pas chargée, le formulaire est marqué occupé (bouton verrouillé + cercle)
 *  et un nouvel envoi est ignoré. Sans JavaScript, il reste un formulaire HTML classique. */
export function FormulaireGet(props: ComponentProps<'form'>) {
  const router = useRouter()
  const chemin = usePathname()
  const [enCours, demarrer] = useTransition()

  function envoyer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (enCours) return
    const q = new URLSearchParams()
    const dates = new Set([...e.currentTarget.querySelectorAll<HTMLInputElement>('input[data-date]')].map((c) => c.name))
    new FormData(e.currentTarget).forEach((v, k) => {
      if (typeof v !== 'string' || v === '') return
      const j = dates.has(k) && /^(\d{2})-(\d{2})-(\d{4})$/.exec(v.trim())   // jj-mm-aaaa saisi → aaaa-mm-jj dans l'URL
      q.set(k, j ? `${j[3]}-${j[2]}-${j[1]}` : v)
    })
    demarrer(() => router.push(q.size ? `${chemin}?${q}` : chemin, { scroll: false }))
  }
  return <form {...props} onSubmit={envoyer} aria-busy={enCours} />
}

/** Téléchargement d'un export (PDF / Excel) : bouton verrouillé avec un cercle jusqu'à la fin du fichier. */
export function Telecharger({ href, className, children }: { href: string; className: string; children: ReactNode }) {
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(false)

  async function telecharger() {
    if (enCours) return
    setEnCours(true)
    setErreur(false)
    try {
      const r = await fetch(href)
      if (!r.ok) throw new Error(String(r.status))
      const nom = /filename="([^"]+)"/.exec(r.headers.get('content-disposition') ?? '')?.[1] ?? 'rapport'
      const url = URL.createObjectURL(await r.blob())
      Object.assign(document.createElement('a'), { href: url, download: nom }).click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      setErreur(true)
    } finally {
      setEnCours(false)
    }
  }
  return (
    <button type="button" className={className} onClick={telecharger} disabled={enCours} aria-busy={enCours}>
      {enCours && <span className="cercle" aria-hidden="true" />}
      {erreur ? 'Échec — réessayer' : children}
    </button>
  )
}

const versFr = (iso?: string) => (iso && /^\d{4}-\d{2}-\d{2}/.test(iso) ? `${iso.slice(8, 10)}-${iso.slice(5, 7)}-${iso.slice(0, 4)}` : iso ?? '')
const versIso = (fr: string) => { const j = /^(\d{2})-(\d{2})-(\d{4})$/.exec(fr.trim()); return j ? `${j[3]}-${j[2]}-${j[1]}` : '' }

/** Date en jj-mm-aaaa : saisie au clavier, ou choix dans le calendrier (bouton) ; FormulaireGet la remet en aaaa-mm-jj dans l'URL. */
export function ChampDate({ name, valeur, ...attrs }: { name: string; valeur?: string; 'aria-label'?: string }) {
  const [texte, setTexte] = useState(versFr(valeur))
  const calendrier = useRef<HTMLInputElement>(null)
  function ouvrir() {
    const c = calendrier.current
    if (!c) return
    c.value = versIso(texte)
    try { c.showPicker() } catch { c.focus() }
  }
  return (
    <span className="champ-date">
      <input name={name} type="text" inputMode="numeric" placeholder="jj-mm-aaaa" pattern="\d{2}-\d{2}-\d{4}" title="Date au format jj-mm-aaaa"
        data-date="" className="date" value={texte} onChange={(e) => setTexte(e.target.value)} {...attrs} />
      <button type="button" className="ouvrir-calendrier" onClick={ouvrir} aria-label={`Choisir dans le calendrier${attrs['aria-label'] ? ` (${attrs['aria-label']})` : ''}`}>
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4" /></svg>
      </button>
      <input ref={calendrier} type="date" tabIndex={-1} aria-hidden="true" className="calendrier-cache" onChange={(e) => e.target.value && setTexte(versFr(e.target.value))} />
    </span>
  )
}
