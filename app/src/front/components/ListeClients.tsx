'use client'

// Liste de clients perdus ou gagnés (onglet Analyse des Ventes) : 8 clients par page, pages côte à côte dans une
// piste à défilement horizontal (glisser, molette ou flèches ‹ ›), le compteur suit la page affichée.
import { useRef, useState } from 'react'
import { court, date } from '../lib/format'

export type ClientListe = { code: string; nom: string; ca_ht: number; date: string; commercial: string; statut?: string }

export function ListeClients({ titre, sous, colonneCa, sens, clients, total, vide, parPage = 8 }: {
  titre: string; sous: string; colonneCa: string; sens: 'perdu' | 'gagne'; clients: ClientListe[]; total: number; vide: string; parPage?: number
}) {
  const piste = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState(0)
  const pages = Array.from({ length: Math.ceil(clients.length / parPage) }, (_, i) => clients.slice(i * parPage, (i + 1) * parPage))
  const max = Math.max(...clients.map((c) => Math.abs(c.ca_ht)), 1)
  const signe = (v: number) => (v < 0 || sens === 'perdu' ? '−' : '+') + court(Math.abs(v))
  const aller = (p: number) => piste.current?.scrollTo({ left: p * piste.current.clientWidth,
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  const suivre = () => { const el = piste.current; if (el && el.clientWidth) setPage(Math.round(el.scrollLeft / el.clientWidth)) }
  const debut = page * parPage + 1, fin = Math.min(clients.length, (page + 1) * parPage)

  return (
    <section className={`carte liste-clients ${sens}`}>
      <div className="lc-titre"><h2>{titre}</h2><span className="doux petit">{sous}</span></div>
      {clients.length ? (
        <>
          <div className="lc-entete" aria-hidden="true"><span>#</span><span>Client</span><span>{colonneCa}</span></div>
          <div className="lc-piste" ref={piste} onScroll={suivre} tabIndex={0} role="region" aria-label={`${titre} : faire défiler horizontalement pour voir plus de clients`}>
            {pages.map((lot, i) => (
              <ol key={i} className="lc-page" start={i * parPage + 1} aria-label={`Clients ${i * parPage + 1} à ${i * parPage + lot.length}`}>
                {lot.map((c, j) => (
                  <li key={c.code} className="lc-ligne">
                    <span className="lc-rang">{i * parPage + j + 1}</span>
                    <span className="lc-client">
                      <span className="lc-nom"><strong title={c.nom}>{c.nom}</strong>{c.statut && <span className={c.statut === 'nouveau' ? 'lc-badge nouveau' : 'lc-badge reactive'}>{c.statut}</span>}</span>
                      <span className="lc-detail">{c.code} · {c.commercial}</span>
                    </span>
                    <span className="lc-montant"><strong>{signe(c.ca_ht)}</strong><span>le {date(c.date)}</span></span>
                    <span className="lc-barre" aria-hidden="true"><span style={{ width: `${Math.max(1.5, (Math.abs(c.ca_ht) / max) * 100)}%` }} /></span>
                  </li>
                ))}
              </ol>
            ))}
          </div>
          <div className="lc-pied">
            <span className="lc-nav">
              <button type="button" onClick={() => aller(page - 1)} disabled={page === 0} aria-label="Clients précédents">‹</button>
              <span aria-live="polite">{debut}–{fin} sur {clients.length}</span>
              <button type="button" onClick={() => aller(page + 1)} disabled={page >= pages.length - 1} aria-label="Clients suivants">›</button>
            </span>
            <span>Total <strong>{signe(total)}</strong></span>
          </div>
        </>
      ) : <p className="vide">{vide}</p>}
    </section>
  )
}
