// Onglets « Analyse » des pages Ventes et Achats (vues analyse_ventes / analyse_achats de l'API, api/bi/vues_analyse.py).
import type { CSSProperties, ReactNode } from 'react'
import { vue } from '../lib/api'
import { annees, court, date, entier, mad, pct } from '../lib/format'
import { lien, lire, type Params } from '../lib/params'
import { Carte, Colonnes, Kpis, Onglets, Puce, Tableau } from './ui'
import { ListeClients } from './ListeClients'

const N0 = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

/** Barre de pourcentage dans une cellule (valeur à droite). */
function Taux({ v, max = 100, couleur }: { v: number | null; max?: number; couleur?: string }) {
  if (v == null) return <span className="doux">N/A</span>
  return (
    <span className="part">
      <span className="piste"><span style={{ width: `${Math.max(2, Math.min(100, (Math.abs(v) / (max || 1)) * 100))}%`, background: couleur }} /></span>
      {pct(v)}
    </span>
  )
}

const tauxMarge = (t: number | null) => <Taux v={t} couleur={t == null ? undefined : t >= 30 ? 'var(--bon)' : t >= 20 ? 'var(--accent)' : 'var(--mauvais)'} />

/** Pont N-1 → N : clients N-1, perdus, nouveaux, réactivés, clients N (barres flottantes à la bonne hauteur). */
function Pont({ a, anN, anN1 }: { a: any; anN: string; anN1: string }) {
  const max = Math.max(a.actifs_n1, a.actifs_n, 1)
  const h = (v: number) => `${(v / max) * 82}%`   // 82 % de la zone : place pour l'étiquette au-dessus
  const apresPerte = a.actifs_n1 - a.perdus, apresNouveaux = apresPerte + a.nouveaux
  const etapes = [
    { nom: `Clients ${anN1}`, libelle: entier(a.actifs_n1), de: 0, a: a.actifs_n1, cls: 'acq-total-n1' },
    { nom: 'Perdus', libelle: `−${entier(a.perdus)}`, de: apresPerte, a: a.actifs_n1, cls: 'acq-perdus' },
    { nom: 'Nouveaux', libelle: `+${entier(a.nouveaux)}`, de: apresPerte, a: apresNouveaux, cls: 'acq-nouveaux' },
    { nom: 'Réactivés', libelle: `+${entier(a.reactives)}`, de: apresNouveaux, a: a.actifs_n, cls: 'acq-reactives' },
    { nom: `Clients ${anN}`, libelle: entier(a.actifs_n), de: 0, a: a.actifs_n, cls: 'acq-total-n' },
  ]
  return (
    <div className="sous-bloc pont">
      <div className="carte-titre"><h3>Pont {anN1} → {anN}</h3><span className="doux petit">nombre de clients</span></div>
      <div className="pont-zone" role="img" aria-label={etapes.map((e) => `${e.nom} : ${e.libelle}`).join(', ')}>
        {etapes.map((e) => (
          <div key={e.nom} className="pont-colonne">
            <span className="pont-repere" style={{ bottom: h(Math.max(e.de, e.a)) }} />
            <span className={`pont-barre ${e.cls}`} style={{ bottom: h(Math.min(e.de, e.a)), height: h(Math.abs(e.a - e.de)) }} />
            <span className={`pont-valeur ${e.cls}`} style={{ bottom: h(Math.max(e.de, e.a)) }}>{e.libelle}</span>
          </div>
        ))}
      </div>
      <div className="pont-noms">{etapes.map((e) => <span key={e.nom}>{e.nom}</span>)}</div>
    </div>
  )
}

/** Composition des clients d'une année : barre empilée (fidèles, perdus, nouveaux, réactivés). */
function Composition({ annee, total, segments }: { annee: string; total: number; segments: [number, string][] }) {
  return (
    <div className="composition">
      <div><strong>{annee}</strong><span className="doux">{entier(total)} clients</span></div>
      <div className="barre-composition">
        {segments.filter(([v]) => v > 0).map(([v, cls]) => (
          <span key={cls} className={`acq-${cls}`} style={{ width: `${total ? (v / total) * 100 : 0}%` }}>{entier(v)}</span>
        ))}
      </div>
    </div>
  )
}

/** Sous-onglets d'une carte (paramètre d'URL `cle`). */
function SousOnglets({ p, chemin, cle, items, defaut }: { p: Params; chemin: string; cle: string; items: [string, string][]; defaut: string }) {
  const actif = lire(p, cle) || defaut
  return <Onglets items={items.map(([v, nom]) => ({ nom, href: lien(chemin, p, { [cle]: v }), actif: actif === v }))} />
}

// ---------------------------------------------------------------------------------------------------------------
// Ventes
// ---------------------------------------------------------------------------------------------------------------
export async function AnalyseVentes({ p, chemin, du, au }: { p: Params; chemin: string; du: string; au: string }) {
  const r = await vue('analyse_ventes', { date_from: du, date_to: au })
  if (!r) return <p className="vide">Analyse indisponible.</p>
  const a = r.acquisition
  const n1 = `du ${date(r.periode.du_n1)} au ${date(r.periode.au_n1)}`
  const anN = annees(r.periode.du, r.periode.au), anN1 = annees(r.periode.du_n1, r.periode.au_n1)   // années réelles, pas « N » / « N-1 »
  const mv = lire(p, 'mv') || 'commercial'
  const av = lire(p, 'av') || 'client'
  const marges: any[] = r.marges[mv === 'famille' ? 'familles' : mv === 'article' ? 'articles' : 'commerciaux'] ?? []
  // Part du CA vendue sans coût connu dans Sage : marge surestimée d'autant (signalée au-delà de 5 %)
  const partSansCout = (m: any) => (m.ca_ht > 0 ? (m.ca_sans_cout / m.ca_ht) * 100 : 0)
  const sansCout = marges.filter((m) => partSansCout(m) > 5).length
  const t = r.avoirs_retours.totaux
  const saison: any[] = r.saisonnalite
  const max = Math.max(...saison.flatMap((s) => s.mois.filter((v: number | null) => v != null && v > 0)), 1)
  const chaleur = (v: number | null) => {
    if (v == null) return <span className="doux">—</span>
    const k = Math.max(0, v) / max
    return (
      <span className="case-chaleur" title={`${mad(v)} MAD HT`}
        style={{ background: `color-mix(in srgb, var(--accent) ${Math.round(8 + 80 * k)}%, #fff)`, color: k > 0.55 ? '#fff' : 'var(--texte)' } as CSSProperties}>
        {N0.format(v / 1000)}
      </span>
    )
  }

  return (
    <>
      <Carte titre="Acquisition et attrition" note={`clients ayant acheté · ${anN} comparé à la même période de ${anN1} (${n1})`}>
        <div className="kpis-grands">
        <Kpis items={[
          { nom: `Clients actifs ${anN}`, v: entier(a.actifs_n),
            sous: <span className={a.actifs_n < a.actifs_n1 ? 'mauvais fort' : 'bon fort'}>{a.actifs_n < a.actifs_n1 ? '▼' : '▲'} {a.actifs_n - a.actifs_n1 > 0 ? '+' : ''}{entier(a.actifs_n - a.actifs_n1)} vs {anN1} ({entier(a.actifs_n1)})</span> },
          { nom: 'Taux de rétention', v: pct(a.actifs_n1 ? (a.fideles / a.actifs_n1) * 100 : null), sous: `${entier(a.fideles)} clients de ${anN1} fidèles en ${anN}` },
          { nom: "Taux d'attrition", v: pct(a.actifs_n1 ? (a.perdus / a.actifs_n1) * 100 : null), ton: 'mauvais', sous: `${entier(a.perdus)} clients de ${anN1} perdus en ${anN}` },
          { nom: "Taux d'acquisition", v: pct(a.actifs_n ? ((a.nouveaux + a.reactives) / a.actifs_n) * 100 : null),
            sous: `${entier(a.nouveaux + a.reactives)} nouveaux ou réactivés sur ${entier(a.actifs_n)}` },
        ]} />
        </div>
        <div className="acq-grille">
          <Pont a={a} anN={anN} anN1={anN1} />
          <div className="sous-bloc">
            <h3>Composition des clients</h3>
            <Composition annee={anN1} total={a.actifs_n1} segments={[[a.fideles, 'fideles'], [a.perdus, 'perdus']]} />
            <Composition annee={anN} total={a.actifs_n} segments={[[a.fideles, 'fideles'], [a.nouveaux, 'nouveaux'], [a.reactives, 'reactives']]} />
            <div className="legende">
              <span><i className="acq-fideles" />Fidèles</span><span><i className="acq-perdus" />Perdus</span>
              <span><i className="acq-nouveaux" />Nouveaux</span><span><i className="acq-reactives" />Réactivés</span>
            </div>
            <div className="impact-ca">
              <h3>Impact sur le CA HT</h3>
              <div><span><i className="acq-nouveaux" />Nouveaux clients (CA {anN})</span><strong className="accent-texte">+{court(a.ca_nouveaux)}</strong></div>
              <div><span><i className="acq-reactives" />Clients réactivés (CA {anN})</span><strong className="accent-texte">+{court(a.ca_reactives)}</strong></div>
              <div><span><i className="acq-perdus" />Clients perdus (leur CA {anN1})</span><strong className="mauvais">−{court(a.ca_perdus_n1)}</strong></div>
              {(() => {
                const solde = (a.ca_nouveaux ?? 0) + (a.ca_reactives ?? 0) - (a.ca_perdus_n1 ?? 0)
                return <div className={`solde ${solde < 0 ? 'negatif' : 'positif'}`}><strong>Solde clients gagnés − perdus</strong><strong>{solde < 0 ? '−' : '+'}{court(Math.abs(solde))}</strong></div>
              })()}
            </div>
          </div>
        </div>
      </Carte>

      <ConcentrationClients c={r.concentration} du={r.periode.du} au={r.periode.au} />

      <div className="grille">
        <ListeClients sens="perdu" titre="Clients perdus à relancer" clients={r.clients_perdus} total={a.ca_perdus_n1}
          sous={`${entier(a.perdus)} clients de ${anN1} sans facture en ${anN}, du plus gros au plus petit CA ${anN1}`}
          colonneCa={`CA ${anN1} · dernière facture`} vide={`Aucun client de ${anN1} perdu en ${anN}.`} />
        <ListeClients sens="gagne" titre="Clients gagnés" clients={r.clients_gagnes} total={(a.ca_nouveaux ?? 0) + (a.ca_reactives ?? 0)}
          sous={`${entier(a.nouveaux)} nouveaux et ${entier(a.reactives)} réactivés, du plus gros au plus petit CA ${anN}`}
          colonneCa={`CA ${anN} · 1ʳᵉ facture ${anN}`} vide={`Aucun nouveau client ni client réactivé en ${anN}.`} />
      </div>

      <Carte titre="Marge" note={`total : ${court(r.marges.total.marge)} · ${pct(r.marges.total.taux_marge)} du CA HT`}>
        <SousOnglets p={p} chemin={chemin} cle="mv" defaut="commercial" items={[['commercial', 'Par commercial'], ['famille', 'Par famille'], ['article', 'Par article']]} />
        <p className="doux petit">Marge brute = CA HT − quantité livrée × coût (prix de revient, sinon CMUP, sinon prix d&apos;achat) : même calcul que le Tableau de Bord.</p>
        {sansCout > 0 && (
          <div className="avertissement" role="note">Pour {entier(sansCout)} ligne{sansCout > 1 ? 's' : ''} du tableau, plus de 5 % du CA est vendu sans coût dans Sage (prix d&apos;achat à 0) : la marge y est surestimée.</div>
        )}
        <Tableau
          colonnes={[{ nom: mv === 'famille' ? 'Famille' : mv === 'article' ? 'Article' : 'Commercial' }, { nom: 'CA HT', droite: true, largeur: '130px' },
            { nom: 'Marge brute', droite: true, largeur: '130px' }, { nom: 'Taux de marge', droite: true, largeur: '170px' }]}
          lignes={marges.map((m) => ({
            cellules: [<span key="n">{m.nom}{partSansCout(m) > 5 && <> <Puce ton="mauvais">{pct(partSansCout(m))} sans coût</Puce></>}</span>, mad(m.ca_ht),
              <strong key="m" className={m.marge < 0 ? 'mauvais' : undefined}>{mad(m.marge)}</strong>, tauxMarge(m.taux_marge)],
          }))}
          vide="Aucune vente sur la période."
        />
      </Carte>

      <Carte titre="Taux d'avoirs et de retours" note={`${entier(t.avoirs)} avoirs (${pct(t.taux_avoirs)} du CA) · ${entier(t.retours)} bons de retour (${pct(t.taux_retours)} des factures)`}>
        <SousOnglets p={p} chemin={chemin} cle="av" defaut="client" items={[['client', 'Par client'], ['article', 'Par article']]} />
        {av === 'article' ? (
          <>
            <p className="doux petit">Quantités en avoir et retournées, rapportées aux quantités facturées de la période.</p>
            <Tableau
              colonnes={[{ nom: 'Réf.', largeur: '130px' }, { nom: 'Désignation' }, { nom: 'Qté vendue', droite: true, largeur: '96px' },
                { nom: 'Qté en avoir', droite: true, largeur: '100px' }, { nom: "Taux d'avoir", droite: true, largeur: '110px' },
                { nom: 'Qté retournée', droite: true, largeur: '110px' }, { nom: 'Taux de retour', droite: true, largeur: '120px' }]}
              lignes={r.avoirs_retours.articles.map((x: any) => ({
                cellules: [x.ar_ref, x.designation, entier(x.qte_vendue), entier(x.qte_avoir),
                  <span key="a" className={x.taux_avoir > 0 ? 'mauvais fort' : undefined}>{pct(x.taux_avoir)}</span>, entier(x.qte_retour),
                  <span key="r" className={x.taux_retour > 0 ? 'mauvais fort' : undefined}>{pct(x.taux_retour)}</span>],
              }))}
              vide="Aucun avoir ni retour sur la période."
            />
          </>
        ) : (
          <>
            <p className="doux petit">Taux d&apos;avoirs = montant des avoirs ÷ montant facturé ; taux de retours = bons de retour ÷ factures.</p>
            <Tableau
              colonnes={[{ nom: 'Code', largeur: '96px' }, { nom: 'Client' }, { nom: 'Factures', droite: true, largeur: '80px' }, { nom: 'Avoirs', droite: true, largeur: '70px' },
                { nom: 'Montant avoirs', droite: true, largeur: '120px' }, { nom: "Taux d'avoirs", droite: true, largeur: '110px' },
                { nom: 'Retours', droite: true, largeur: '74px' }, { nom: 'Taux de retours', droite: true, largeur: '120px' }]}
              lignes={[...r.avoirs_retours.clients.map((x: any) => ({
                cellules: [x.code, x.nom, entier(x.factures), entier(x.avoirs), mad(x.montant_avoirs),
                  <span key="a" className={x.taux_avoirs > 0 ? 'mauvais fort' : undefined}>{pct(x.taux_avoirs)}</span>, entier(x.retours),
                  <span key="r" className={x.taux_retours > 0 ? 'mauvais fort' : undefined}>{pct(x.taux_retours)}</span>],
              })), { total: true, cellules: ['', 'Toute la clientèle', entier(t.factures), entier(t.avoirs), mad(t.montant_avoirs), pct(t.taux_avoirs), entier(t.retours), pct(t.taux_retours)] }]}
            />
          </>
        )}
      </Carte>

      <Carte titre="Saisonnalité du CA HT" note="en KMAD · plus la case est foncée, plus le mois est fort">
        <div className="defile">
          <table className="tableau chaleur">
            <colgroup><col style={{ width: '64px' }} />{MOIS.map((m) => <col key={m} />)}<col style={{ width: '110px' }} /></colgroup>
            <thead><tr><th scope="col">Année</th>{MOIS.map((m) => <th key={m} scope="col">{m}</th>)}<th scope="col" className="droite">Total</th></tr></thead>
            <tbody>
              {saison.map((s) => (
                <tr key={s.annee}>
                  <th scope="row">{s.annee}</th>
                  {s.mois.map((v: number | null, i: number) => <td key={i}>{chaleur(v)}</td>)}
                  <td className="droite fort">{court(s.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Carte>
    </>
  )
}

// ---------------------------------------------------------------------------------------------------------------
// Concentration : fournisseurs (Achats) ou clients (Ventes) — Pareto, répartition, HHI
// ---------------------------------------------------------------------------------------------------------------
type Qui = 'fournisseur' | 'client'
const seuilsHhi = (qui: Qui): [string, string, (h: number) => boolean][] => [
  ['moins de 1 500', qui === 'client' ? 'CA bien réparti, faible dépendance' : 'achats bien répartis, faible dépendance', (h) => h < 1500],
  ['1 500 à 2 500', 'concentration modérée', (h) => h >= 1500 && h <= 2500],
  ['plus de 2 500', `forte dépendance à 1 ou 2 ${qui}s`, (h) => h > 2500 && h < 10000],
  ['10 000', `un seul ${qui}`, (h) => h >= 10000],
]
const niveauHhi = (h: number | null) => (h == null ? '—' : h < 1500 ? 'concentration faible (moins de 1 500)' : h <= 2500 ? 'concentration modérée (1 500 à 2 500)' : 'concentration forte (plus de 2 500)')

/** Bouton « ? » du HHI : ouvre le tableau de lecture (élément <details>, sans JavaScript). */
function AideHhi({ hhi, qui = 'fournisseur' }: { hhi: number | null; qui?: Qui }) {
  return (
    <details className="aide-kpi">
      <summary aria-label="Comment lire cet indicateur">?</summary>
      <div className="bulle-aide" role="note">
        <strong>Comment lire le HHI</strong>
        <p>{qui === 'client'
          ? "Somme des carrés des parts (en %) de chaque client : les gros clients pèsent beaucoup plus que les petits. Plus l'indice est élevé, plus votre CA dépend de peu de clients. Suivi dans le temps, il montre si la dépendance augmente."
          : "Somme des carrés des parts (en %) de chaque fournisseur : les gros fournisseurs pèsent beaucoup plus que les petits. Plus l'indice est élevé, plus vos achats dépendent de peu de fournisseurs. Suivi dans le temps, il montre si la dépendance augmente."}</p>
        <table>
          <thead><tr><th scope="col">HHI</th><th scope="col">Signification</th></tr></thead>
          <tbody>
            {seuilsHhi(qui).map(([seuil, sens, ici]) => {
              const oui = hhi != null && ici(hhi)
              return <tr key={seuil} className={oui ? 'ici' : undefined}><td>{seuil}</td><td>{sens}{oui && ` · vous êtes ici (${entier(Math.round(hhi!))})`}</td></tr>
            })}
          </tbody>
        </table>
      </div>
    </details>
  )
}

type ColonnePareto = { nom: string; etiquette: string; v: number; part: number; dedans: boolean }

/** Courbe de Pareto : part de chaque colonne (barres, en couleur celles des 80 %), cumul (courbe) et seuil de 80 %. */
function Pareto({ cols, legende, seuil, lecture, seuilFonce }: { cols: ColonnePareto[]; legende: string; seuil: string; lecture: ReactNode; seuilFonce?: boolean }) {
  const maxPart = Math.max(...cols.map((c) => c.part), 1)
  const BARRE = 58, CUMUL = 88   // hauteurs maximales (% de la zone) : barres ; cumul à 100 %
  let cumul = 0
  const points: string[] = []
  const colonnes = cols.map((c, i) => {
    cumul += c.part
    points.push(`${(((i + 0.5) / cols.length) * 100).toFixed(2)},${(100 - (cumul * CUMUL) / 100).toFixed(2)}`)
    return { ...c, cumul }
  })
  return (
    <div className="sous-bloc pareto">
      <div className="carte-titre"><h3>Courbe de Pareto</h3>
        <span className="legende"><span><i className="b" />{legende}</span><span><i className="trait" />cumul</span></span></div>
      <div className={seuilFonce ? 'pareto-zone seuil-fonce' : 'pareto-zone'} role="img" aria-label={colonnes.map((c) => `${c.nom} : ${pct(c.part)}, cumul ${pct(c.cumul)}`).join(' ; ')}>
        <span className="pareto-seuil" style={{ bottom: `${(80 * CUMUL) / 100}%` }}><span>{seuil}</span></span>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline points={points.join(' ')} /></svg>
        <div className="pareto-colonnes">
          {colonnes.map((c) => (
            <div key={c.nom} className="pareto-colonne" title={`${c.nom} · ${mad(c.v)} MAD · ${pct(c.part)} · cumul ${pct(c.cumul)}`}>
              <span className={c.dedans ? 'barre dedans' : 'barre'} style={{ height: `${Math.max(1.2, (c.part / maxPart) * BARRE)}%` }} />
              <span className={c.dedans ? 'valeur dedans' : 'valeur'} style={{ bottom: `${Math.max(1.2, (c.part / maxPart) * BARRE)}%` }}>{pct(c.part)}</span>
              <span className="point" style={{ bottom: `${(c.cumul * CUMUL) / 100}%` }} />
            </div>
          ))}
        </div>
      </div>
      <div className="pareto-noms">{colonnes.map((c) => <span key={c.nom} title={c.nom} className={c.dedans ? 'dedans' : undefined}>{c.etiquette}</span>)}</div>
      <p className="doux petit">{lecture}</p>
    </div>
  )
}

type Segment = { nom: string; etiquette: string; detail?: string; v: number; part: number; couleur: string; cTrait?: string; gris: boolean }

/** Anneau de répartition, étiquettes autour. `alignees` : étiquettes en deux colonnes, écartées d'au moins 36 px
 *  (plusieurs petites parts voisines, sinon elles se chevauchent). */
function Repartition({ titre, sous, segs, centre, centreSous, alignees }: { titre: string; sous: string; segs: Segment[]; centre: string; centreSous: string; alignees?: boolean }) {
  const C = { x: 210, y: 160 }
  let avant = 0
  const geo = segs.map((s) => {
    const ang = ((-90 + (360 * (avant + s.part / 2)) / 100) * Math.PI) / 180
    const cos = Math.cos(ang), sin = Math.sin(ang)
    const g = { ...s, offset: -avant, cos, sin, droite: cos >= 0, ax: C.x + 76 * cos, ay: C.y + 76 * sin, trait: '', lx: 0, ly: 0 }
    avant += s.part
    return g
  })
  if (alignees) {
    for (const droite of [true, false]) {
      const cote = geo.filter((g) => g.droite === droite).sort((a, b) => a.sin - b.sin)
      const ys: number[] = []
      for (const g of cote) ys.push(Math.max(C.y + 92 * g.sin, (ys.at(-1) ?? -Infinity) + 36))
      const deb = ys.length ? ys[ys.length - 1] - 300 : 0
      cote.forEach((g, i) => {
        const y = deb > 0 ? ys[i] - deb : ys[i], dx = droite ? 312 : 108, cx = dx + (droite ? -12 : 12)
        g.trait = [[g.ax, g.ay], [C.x + 92 * g.cos, C.y + 92 * g.sin], [cx, y], [dx, y]].map(([x, yy]) => `${x.toFixed(1)},${yy.toFixed(1)}`).join(' ')
        g.lx = dx + (droite ? 5 : -5) - C.x
        g.ly = y - C.y
      })
    }
  } else {
    for (const g of geo) {
      const [bx, by] = [C.x + 98 * g.cos, C.y + 98 * g.sin], cx = bx + (g.droite ? 14 : -14)
      g.trait = `${g.ax.toFixed(1)},${g.ay.toFixed(1)} ${bx.toFixed(1)},${by.toFixed(1)} ${cx.toFixed(1)},${by.toFixed(1)}`
      g.lx = cx + (g.droite ? 5 : -5) - C.x
      g.ly = by - C.y
    }
  }
  return (
    <div className="sous-bloc repartition">
      <h3>{titre}</h3>
      <span className="doux petit">{sous}</span>
      <div className="repartition-zone">
        <svg viewBox="0 0 420 320" preserveAspectRatio="xMidYMid meet" role="img" aria-label={geo.map((g) => `${g.nom} : ${pct(g.part)}`).join(', ')}>
          {geo.map((g) => (
            <circle key={g.nom} cx={C.x} cy={C.y} r="62" pathLength={100} fill="none" stroke={g.couleur} strokeWidth="26"
              strokeDasharray={`${g.part.toFixed(3)} ${(100 - g.part).toFixed(3)}`} strokeDashoffset={g.offset.toFixed(3)} transform={`rotate(-90 ${C.x} ${C.y})`} />
          ))}
          {geo.map((g) => {
            const trait = g.gris ? '#a1a1aa' : g.cTrait ?? g.couleur
            return (
              <g key={`t-${g.nom}`} stroke={trait} fill={trait}>
                <polyline points={g.trait} fill="none" strokeWidth="1.5" strokeLinejoin="round" />
                <circle cx={g.ax} cy={g.ay} r="3" stroke="none" />
              </g>
            )
          })}
        </svg>
        <span className="repartition-centre"><strong>{centre}</strong><span>{centreSous}</span></span>
        {geo.map((g) => (
          <span key={`l-${g.nom}`} className={g.droite ? 'etiquette droite' : 'etiquette gauche'} title={`${g.nom}${g.detail ? ` · ${g.detail}` : ''} · ${mad(g.v)} MAD HT · ${pct(g.part)}`}
            style={{ left: `calc(50% + ${g.lx.toFixed(1)}px)`, top: `calc(50% + ${g.ly.toFixed(1)}px)` }}>
            <strong>{g.etiquette}</strong>
            <span className={g.gris ? 'doux' : 'accent-texte'}>{court(g.v)} · {pct(g.part)}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

/** Concentration des clients (Ventes) : KPI, Pareto par tranches de 10 % des clients, répartition du CA. */
function ConcentrationClients({ c, du, au }: { c: any; du: string; au: string }) {
  if (!c.clients) return <Carte titre="Concentration des clients"><p className="vide">Aucune vente sur la période.</p></Carte>
  const n80: number = c.nb_pour_80, t0 = c.tranches[0], premier = c.premiers[0]
  const tranche80 = c.tranches.findIndex((t: any) => t.de <= n80 && n80 <= t.a) + 1
  const autres = c.clients - Math.max(n80, c.premiers.length)
  const segs: Segment[] = [
    ...c.premiers.map((x: any, i: number) => ({ nom: x.nom, etiquette: x.nom.split(' ').slice(0, 2).join(' '), detail: `${i + 1}${i === 0 ? 'er' : 'ᵉ'} client`, v: x.ca_ht, part: x.part,
      couleur: `color-mix(in srgb, var(--accent) ${[100, 82, 66, 52, 40][i]}%, #fff)`, gris: false })),
    ...(n80 > c.premiers.length ? [{ nom: `Du ${c.premiers.length + 1}ᵉ au ${n80}ᵉ client`, etiquette: `Du ${c.premiers.length + 1}ᵉ au ${n80}ᵉ client`,
      detail: `${entier(n80 - c.premiers.length)} clients, jusqu'à 80 % du CA`, v: c.ca_jusqu_80, part: (c.ca_jusqu_80 / c.total_ht) * 100,
      couleur: 'color-mix(in srgb, var(--accent) 22%, #fff)', cTrait: 'var(--accent)', gris: false }] : []),
    ...(autres > 0 ? [{ nom: `${entier(autres)} autres clients`, etiquette: `${entier(autres)} autres clients`, detail: 'au-delà des 80 %',
      v: c.ca_autres, part: (c.ca_autres / c.total_ht) * 100, couleur: '#d4d4d8', gris: true }] : []),
  ]
  return (
    <Carte titre="Concentration des clients" note={`CA HT net par client · factures du ${date(du)} au ${date(au)} · ${court(c.total_ht)}`}>
      <div className="kpis-grands">
        <Kpis items={[
          { nom: 'Part du 1er client', v: pct(premier?.part), sous: `${premier?.nom ?? '—'} · ${court(premier?.ca_ht)}` },
          { nom: 'Clients pour 80 % du CA', v: entier(n80), sous: `sur ${entier(c.clients)} clients facturés (${pct((n80 / c.clients) * 100)})` },
          { nom: 'Concentration (HHI)', v: entier(c.hhi == null ? null : Math.round(c.hhi)), ton: c.hhi == null ? undefined : c.hhi < 1500 ? 'bon' : c.hhi > 2500 ? 'mauvais' : undefined,
            sous: niveauHhi(c.hhi), aide: <AideHhi hhi={c.hhi} qui="client" /> },
          { nom: 'Les 10 % premiers clients', v: pct(t0?.part), sous: `les ${entier(t0?.a)} plus gros clients sur ${entier(c.clients)}` },
        ]} />
      </div>
      <div className="acq-grille">{/* mêmes colonnes que la carte Acquisition : Pareto aligné sur le Pont, répartition sur la Composition */}
        <Pareto seuilFonce legende="part du CA de la tranche" seuil="80 % du CA"
          cols={c.tranches.map((t: any) => ({ nom: `clients ${t.de}-${t.a}`, etiquette: t.de === t.a ? String(t.de) : `${t.de}-${t.a}`, v: t.ca_ht, part: t.part, dedans: t.de <= n80 }))}
          lecture={`Lecture : chaque barre regroupe 10 % des clients${c.clients >= 20 ? ` (environ ${entier(Math.round(c.clients / 10))})` : ''}, du plus gros au plus petit. ${t0.a === 1 ? 'Le 1er client fait' : `Les ${entier(t0.a)} premiers font`} ${pct(t0.part)} du CA ; la courbe atteint 80 % au ${n80 === 1 ? '1er' : `${entier(n80)}ᵉ`} client, dans la ${tranche80 === 1 ? '1ʳᵉ' : `${tranche80}ᵉ`} tranche. Survolez une barre pour le détail.`} />
        <Repartition alignees titre="Répartition du CA" sous="CA HT des 5 premiers clients, puis jusqu'à 80 %, puis tous les autres"
          segs={segs} centre={entier(n80)} centreSous="clients font 80 % du CA" />
      </div>
    </Carte>
  )
}

// ---------------------------------------------------------------------------------------------------------------
// Achats (directeur)
// ---------------------------------------------------------------------------------------------------------------
export async function AnalyseAchats({ du, au }: { du: string; au: string }) {
  const r = await vue('analyse_achats', { date_from: du, date_to: au })
  if (!r) return <p className="vide">Analyse indisponible.</p>
  const d = r.dependance
  // Pareto : 10 premiers fournisseurs + les autres ; répartition : ceux qui font 80 % + les autres
  const f: any[] = d.fournisseurs, f80 = f[Math.max(0, d.nb_pour_80 - 1)]
  const somme = (l: any[], k: string) => l.reduce((t, x) => t + x[k], 0)
  const colsF: ColonnePareto[] = [...f.slice(0, 10), ...(f.length > 10 ? [{ nom: `${f.length - 10} autres`, achats_ht: somme(f.slice(10), 'achats_ht'), part: somme(f.slice(10), 'part') }] : [])]
    .map((x, i) => ({ nom: x.nom, etiquette: /^\d/.test(x.nom) ? x.nom : x.nom.split(/[ .]/)[0], v: x.achats_ht, part: x.part, dedans: i < d.nb_pour_80 }))
  const topF = f.slice(0, Math.max(1, d.nb_pour_80)), resteF = f.slice(topF.length)
  const segsF: Segment[] = [...topF.map((x, i) => ({ nom: x.nom, etiquette: x.nom.split(' ').slice(0, 2).join(' '), v: x.achats_ht, part: x.part,
    couleur: `color-mix(in srgb, var(--accent) ${[100, 78, 60, 45, 32, 24, 18][Math.min(i, 6)]}%, #fff)`, gris: false })),
    ...(resteF.length ? [{ nom: `${resteF.length} autres fournisseurs`, etiquette: `${resteF.length} autres`, v: somme(resteF, 'achats_ht'), part: somme(resteF, 'part'), couleur: '#d4d4d8', gris: true }] : [])]
  const inf = r.inflation
  const familles: any[] = [...inf.familles].sort((x: any, y: any) => (y.evolution_pct ?? 0) - (x.evolution_pct ?? 0))
  const hausse = familles.find((f) => (f.evolution_pct ?? 0) > 0)
  const baisse = [...familles].reverse().find((f) => (f.evolution_pct ?? 0) < 0)
  const maxInf = Math.max(...inf.familles.map((f: any) => Math.abs(f.evolution_pct ?? 0)), 1)
  const evol = (v: number | null): ReactNode => v == null ? <span className="doux">N/A</span> : (
    <span className="part">
      <span className="piste"><span style={{ width: `${Math.max(3, (Math.abs(v) / maxInf) * 100)}%`, background: v > 0 ? 'var(--mauvais)' : 'var(--bon)' }} /></span>
      <strong className={v > 0 ? 'mauvais' : 'bon'}>{pct(v, true)}</strong>
    </span>
  )

  return (
    <>
      <Carte titre="Dépendance fournisseurs" note={`achats HT de la période · ${court(d.total_ht)}`}>
        <Kpis items={[
          { nom: 'Part du 1er fournisseur', v: pct(d.part_premier), ton: (d.part_premier ?? 0) >= 30 ? 'mauvais' : undefined, sous: `${d.premier ?? '—'} · ${court(d.fournisseurs?.[0]?.achats_ht)}` },
          { nom: 'Fournisseurs pour 80 % des achats', v: entier(d.nb_pour_80), sous: `sur ${entier(d.fournisseurs_actifs)} fournisseurs actifs` },
          { nom: 'Indice de concentration (HHI)', v: entier(d.hhi == null ? null : Math.round(d.hhi)), sous: niveauHhi(d.hhi), aide: <AideHhi hhi={d.hhi} /> },
          { nom: 'Fournisseurs actifs', v: entier(d.fournisseurs_actifs), sous: "au moins une facture d'achat sur la période" },
        ]} />
        {d.fournisseurs.length ? (
          <div className="dep-grille">
            <Pareto legende="part du fournisseur" seuil="80 % des achats" cols={colsF}
              lecture={`Les ${entier(d.nb_pour_80)} premiers fournisseurs (en couleur) font ${pct(f80?.cumul)} des achats ; la courbe franchit 80 % au ${entier(d.nb_pour_80)}ᵉ (${f80?.nom}). Survolez une barre pour le détail.`} />
            <Repartition titre="Répartition des achats" sous="achats HT des fournisseurs qui font 80 %, puis tous les autres" segs={segsF}
              centre={entier(topF.length)} centreSous={`fournisseurs font ${pct(somme(topF, 'part'))} des achats`} />
          </div>
        ) : <p className="vide">Aucun achat sur la période.</p>}
      </Carte>

      <Carte titre="Inflation des prix d'achat par famille" note="premier → dernier prix payé de chaque article, moyenne pondérée par les quantités">
        <Kpis items={[
          { nom: 'Évolution globale des prix', v: inf.global ? pct(inf.global.evolution_pct, true) : 'N/A', ton: inf.global ? (inf.global.evolution_pct > 0 ? 'mauvais' : 'bon') : undefined,
            sous: inf.global ? `${entier(inf.global.articles)} articles achetés à au moins 2 dates` : 'pas assez d\'achats répétés' },
          { nom: 'Famille la plus inflationniste', v: hausse ? pct(hausse.evolution_pct, true) : 'aucune', ton: hausse ? 'mauvais' : undefined,
            sous: hausse ? `${hausse.famille} · ${entier(hausse.articles)} article${hausse.articles > 1 ? 's' : ''}` : 'aucune famille en hausse' },
          { nom: 'Famille en plus forte baisse', v: baisse ? pct(baisse.evolution_pct, true) : 'aucune', ton: baisse ? 'bon' : undefined,
            sous: baisse ? `${baisse.famille} · ${entier(baisse.articles)} article${baisse.articles > 1 ? 's' : ''}` : 'aucune famille en baisse' },
        ]} />
        <Tableau
          colonnes={[{ nom: 'Famille' }, { nom: 'Articles comparés', droite: true, largeur: '140px' }, { nom: 'Achats HT', droite: true, largeur: '130px' },
            { nom: 'Évolution des prix', droite: true, largeur: '210px' }]}
          lignes={familles.map((f: any) => ({ cellules: [f.famille, entier(f.articles), mad(f.achats_ht), evol(f.evolution_pct)] }))}
          vide="Aucun article acheté à au moins deux dates sur la période."
        />
        <p className="doux petit">Rouge : prix en hausse · vert : prix en baisse. Même calcul que « Évolution des prix » des fiches fournisseurs, agrégé par famille.</p>
      </Carte>

      <Carte titre="Fiabilité des délais de livraison" note={`commande → livraison · classement par régularité (livraisons à ± ${r.delais.tolerance_jours} j du délai habituel)`}>
        <Tableau
          colonnes={[{ nom: '#', largeur: '40px' }, { nom: 'Fournisseur' }, { nom: 'Commandes livrées', droite: true, largeur: '130px' },
            { nom: 'Lignes', droite: true, largeur: '70px' }, { nom: 'Délai moyen', droite: true, largeur: '100px' }, { nom: 'Écart type', droite: true, largeur: '90px' },
            { nom: 'Régularité', droite: true, largeur: '160px' }]}
          lignes={r.delais.fournisseurs.map((f: any, i: number) => ({
            cellules: [i + 1, f.nom, entier(f.commandes), entier(f.lignes),
              <strong key="m" title={`délai habituel (médian) : ${entier(Math.round(f.delai_median))} j`}>{entier(Math.round(f.delai_moyen))} j</strong>,
              f.ecart_type == null ? '—' : `± ${(f.ecart_type as number).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} j`,
              <Taux key="r" v={f.regularite_pct} couleur={f.regularite_pct >= 80 ? 'var(--bon)' : f.regularite_pct >= 60 ? '#b45309' : 'var(--mauvais)'} />],
          }))}
          vide="Aucune ligne avec une date de commande et une date de livraison sur la période."
        />
        <p className="doux petit">Délai = date de livraison − date de commande des lignes livrées après la commande (même calcul que les fiches fournisseurs). Sage ne garde pas de date promise : la régularité mesure si le fournisseur livre toujours dans le même délai.</p>
      </Carte>

      <Carte titre="Achats et ventes par famille" note="HT de la période · si les achats dépassent le coût des ventes, le stock de la famille gonfle">
        <Colonnes legende={{ a: 'Coût des ventes', b: 'Achats HT' }}
          groupes={r.achats_ventes.map((f: any) => ({ nom: f.famille, a: f.cout_ventes, b: f.achats_ht }))} />
        <Tableau
          colonnes={[{ nom: 'Famille' }, { nom: 'Achats HT', droite: true, largeur: '120px' }, { nom: 'Ventes HT', droite: true, largeur: '120px' },
            { nom: 'Coût des ventes', droite: true, largeur: '120px' }, { nom: 'Achats ÷ coût', droite: true, largeur: '100px' },
            { nom: 'Achats − coût', droite: true, largeur: '120px' }, { nom: 'Stock', largeur: '100px' }]}
          lignes={r.achats_ventes.map((f: any) => ({
            cellules: [f.famille, mad(f.achats_ht), mad(f.ventes_ht), mad(f.cout_ventes),
              <strong key="r" className={f.cout_ventes > 0 && f.achats_ht > f.cout_ventes ? 'mauvais' : undefined}>{f.cout_ventes > 0 ? pct((f.achats_ht / f.cout_ventes) * 100) : 'N/A'}</strong>,
              <strong key="e" className={f.ecart_stock > 0 ? 'mauvais' : 'bon'}>{mad(f.ecart_stock)}</strong>,
              <Puce key="s" ton={f.ecart_stock > 0 ? 'mauvais' : 'bon'}>{f.ecart_stock > 0 ? 'gonfle' : 'se vide'}</Puce>],
          }))}
          vide="Aucun achat ni vente sur la période."
        />
        <p className="doux petit">Coût des ventes = quantités vendues × coût (même calcul que la marge) : on compare des achats et des sorties au même prix, celui du coût.</p>
      </Carte>
    </>
  )
}
