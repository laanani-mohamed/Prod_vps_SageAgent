import { notFound } from 'next/navigation'
import { Telecharger } from '../../../components/Interactions'
import Page from '../../../components/Page'
import {
  Barres, Carte, Champ, Colonnes, Entete, Filtres, Interdit, Kpis, Pagination, Pile, Tableau,
  type Colonne, type Kpi, type Ligne,
} from '../../../components/ui'
import { api, estCollaborateur, session } from '../../../lib/api'
import { court, date, entier, mad, optionsCommerciaux, pct } from '../../../lib/format'
import { lien, lire, type Params } from '../../../lib/params'
import { filtresRapport, RAPPORTS } from '../../../lib/rapports'

type Section = { titre: string; colonnes: string[]; lignes: any[][] }
type Donnees = {
  titre: string; sous_titre: string; filtres: Record<string, any>; totaux: Record<string, number>
  repartition: { libelle: string; valeur: number; nombre: number }[]; options: Record<string, string[]>; sections: Section[]
}

const TAILLE = 50
const TRANCHES = ['0-60j', '60-90j', '90-120j', '+120j']
const COULEURS_TRANCHES = ['#9ed8db', '#467599', '#1d3354', '#d64045'] // palette du rapport 9
const GROUPES: [string, string][] = [['client', 'Client'], ['region', 'Région'], ['commercial', 'Collaborateur']]
const NOMBRE_DE: Record<string, string> = { client: 'clients', region: 'régions', commercial: 'collaborateurs' }

/** Valeur de la colonne `nom` d'une ligne de section. */
const val = (s: Section, ligne: any[], nom: string) => ligne[s.colonnes.indexOf(nom)]

/** Section en tableau, paginée par 50 ; ligne Total en tête si `totaux` (montants par nom de colonne). */
function TableauSection({ s, p, chemin, cle, totaux, libelleTotal }: {
  s: Section; p: Params; chemin: string; cle: string; totaux?: Record<string, number>; libelleTotal?: string
}) {
  const page = Number(lire(p, cle) || 1)
  const decimales = s.colonnes.map((_, j) => s.lignes.some((l) => typeof l[j] === 'number' && !Number.isInteger(l[j])))
  const nombre = s.colonnes.map((_, j) => s.lignes.some((l) => typeof l[j] === 'number'))
  const fmt = (v: any, j: number) => (typeof v === 'number' ? (decimales[j] ? mad(v) : entier(v)) : v == null || v === '' ? '—' : String(v))
  const colonnes: Colonne[] = s.colonnes.map((c, j) => ({ nom: c, droite: nombre[j] }))
  const lignes: Ligne[] = s.lignes.slice((page - 1) * TAILLE, page * TAILLE).map((l) => ({ cellules: l.map(fmt) }))
  if (totaux && s.lignes.length) {
    lignes.unshift({ total: true, cellules: s.colonnes.map((c, j) => (j === 0 ? 'Total' : j === 1 && libelleTotal ? libelleTotal : c in totaux ? fmt(totaux[c], j) : '')) })
  }
  return (
    <>
      <Tableau colonnes={colonnes} lignes={lignes} />
      <Pagination total={s.lignes.length} page={page} taille={TAILLE} href={(n) => lien(chemin, p, { [cle]: n })} />
    </>
  )
}

function kpis(nom: string, d: Donnees): Kpi[] {
  const t = d.totaux
  const ton = (v?: number) => ((v ?? 0) < 0 ? 'mauvais' : 'bon') as Kpi['ton']
  switch (nom) {
    case 'chiffre_affaire':
      return [
        { nom: `Nombre de ${NOMBRE_DE[d.filtres.group_by]}`, v: entier(t.nombre) },
        { nom: 'CA HT total', v: court(t['CA HT']), sous: `${mad(t['CA HT'])} MAD` },
        { nom: 'Nombre de factures', v: entier(t['Nb Factures']) },
        { nom: 'Moyenne / facture', v: mad(t['Moyenne / Facture']), sous: 'MAD HT' },
      ]
    case 'comparaison_ca':
      return [
        { nom: 'Total', v: entier(t.nombre), sous: 'lignes sur les 2 périodes' },
        { nom: 'CA période 1', v: court(t['CA Période 1']), sous: mad(t['CA Période 1']) },
        { nom: 'CA période 2', v: court(t['CA Période 2']), sous: mad(t['CA Période 2']) },
        { nom: 'Écart', v: court(t['Ecart (MAD)']), ton: ton(t['Ecart (MAD)']) },
        { nom: 'Évolution', v: pct(t['Evolution (%)'], true), ton: ton(t['Evolution (%)']) },
      ]
    case 'balance':
      return [
        { nom: 'Clients', v: entier(t.nombre), sous: 'avec un solde' },
        { nom: 'À nouveau', v: court(t['A Nouveau']), sous: mad(t['A Nouveau']) },
        { nom: 'Mois en cours', v: court(t['En Cours']), sous: mad(t['En Cours']) },
        { nom: 'Solde total', v: court(t.Totale), sous: `${mad(t.Totale)} MAD TTC` },
      ]
    case 'balance_agee':
      return [...TRANCHES.map((c, i) => ({ nom: c.replace('j', ' jours'), v: court(t[c]), sous: mad(t[c]), ton: (i === 3 ? 'mauvais' : undefined) as Kpi['ton'] })),
        { nom: 'Encours total', v: court(t.Totale), sous: `${entier(t.nombre)} clients` }]
    case 'valeur_stock':
      return [
        { nom: 'Valeur totale du stock', v: `${mad(t['Valeur Stock'])} MAD` },
        { nom: 'Lignes article × dépôt', v: entier(t.nombre) },
        { nom: 'Quantité en stock', v: entier(t['Qté Stock']) },
        { nom: 'Dépôts valorisés', v: entier(d.repartition.length) },
      ]
    case 'visite_client': {
      const s7 = d.sections[6]
      const annee = s7?.lignes[0]
      return [
        { nom: 'Bons de commande en cours', v: entier(t['BC en cours']) },
        { nom: 'Factures non réglées', v: entier(t['Factures non réglées']) },
        { nom: 'Reste à payer', v: mad(t['Reste à Payer'] ?? 0), sous: 'MAD TTC', ton: (t['Reste à Payer'] ?? 0) > 0 ? 'mauvais' : undefined },
        { nom: 'CA 6 mois glissants', v: annee ? court(val(s7, annee, 'Total')) : 'N/A',
          sous: annee && val(s7, annee, 'Évolution (%)') != null ? `${pct(val(s7, annee, 'Évolution (%)'), true)} vs ${val(s7, s7.lignes[1], 'Période')}` : undefined,
          ton: annee ? ton(val(s7, annee, 'Évolution (%)')) : undefined },
      ]
    }
    case 'produits_dormants':
      return [
        { nom: 'Produits dormants', v: entier(t.nombre), sous: `inactifs depuis plus de ${d.filtres.mois} mois` },
        { nom: 'Valeur immobilisée', v: court(t['Valeur Stock']), sous: `${mad(t['Valeur Stock'])} MAD` },
        { nom: 'Quantité en stock', v: entier(t['Qté Totale']) },
      ]
    case 'lots_peremption':
      return [
        { nom: `Lots expirant sous ${d.filtres.jours} jours`, v: entier(t.nombre) },
        { nom: 'Quantité restante', v: entier(t['Qté Restante'] ?? 0) },
      ]
    default: // consommation
      return [
        { nom: 'Familles', v: entier(t.familles), sous: 'avec consommation' },
        { nom: 'Articles consommés', v: entier(t.articles), sous: 'au moins une sortie' },
        { nom: 'Quantité totale consommée', v: entier(t['Qté Totale Consommée']), sous: '6 mois glissants' },
      ]
  }
}

export default async function PageRapport({ params, searchParams }: { params: Promise<{ n: string }>; searchParams: Promise<Params> }) {
  const { n } = await params
  const r = RAPPORTS.find((x) => String(x.n) === n)
  if (!r) notFound()
  const p = await searchParams
  const s = await session()
  const collab = estCollaborateur(s)
  const chemin = `/rapports/${r.n}`
  const titre = (sousTitre?: string, actions?: React.ReactNode) => (
    <Entete titre={r.titre} sur={`Rapports BI · Rapport ${r.n}`} badge={<span className="badge-rapport">{r.n}</span>} sousTitre={sousTitre} actions={actions} />
  )
  if ('stock' in r && collab) return <Page accent={r.couleur}>{titre()}<Interdit /></Page>

  const { filtres, coNo } = filtresRapport(r.nom, p)
  const appel = (f: object) => api<Donnees>(`/api/bi/rapports/${r.nom}`, { client_schema: s.client, filtres: f, co_no: coNo })
  const parCommercial = !collab && ['chiffre_affaire', 'comparaison_ca', 'balance', 'balance_agee'].includes(r.nom)
  const [d, repCommercial, repRegion, collaborateurs, clients] = await Promise.all([
    r.nom === 'visite_client' && !filtres.client ? null : appel(filtres),
    r.nom === 'chiffre_affaire' ? appel({ ...filtres, group_by: 'commercial' }) : null,
    r.nom === 'chiffre_affaire' ? appel({ ...filtres, group_by: 'region' }) : null,
    parCommercial ? api('/api/referentiel/collaborateurs', { client_schema: s.client }) : null,
    r.nom === 'visite_client' ? api('/api/referentiel/comptes-tiers', { client_schema: s.client, ct_type: [0] }) : null,
  ])
  const f = d?.filtres ?? {}

  const champCommercial = parCommercial && (
    <Champ label="Commercial" name="commercial" defaut={lire(p, 'commercial')} options={optionsCommerciaux(collaborateurs)} />
  )
  const champsFiltres: Record<string, React.ReactNode> = {
    chiffre_affaire: <>
      <Champ label="Grouper par" name="group_by" defaut={f.group_by} options={GROUPES} />
      <Champ label="Date début" name="date_from" type="date" defaut={f.date_from} />
      <Champ label="Date fin" name="date_to" type="date" defaut={f.date_to} />
      {champCommercial}
    </>,
    comparaison_ca: <>
      <Champ label="Début P1 (référence)" name="date_from_1" type="date" defaut={f.date_from_1} />
      <Champ label="Fin P1" name="date_to_1" type="date" defaut={f.date_to_1} />
      <Champ label="Début P2 (comparée)" name="date_from_2" type="date" defaut={f.date_from_2} />
      <Champ label="Fin P2" name="date_to_2" type="date" defaut={f.date_to_2} />
      <Champ label="Grouper par" name="group_by" defaut={f.group_by} options={GROUPES} />
      {champCommercial}
    </>,
    balance: champCommercial, balance_agee: champCommercial,
    valeur_stock: <>
      <Champ label="Dépôt" name="depot" defaut={lire(p, 'depot')} options={[['', 'Tous'], ...(d?.options.depots ?? []).map((x): [string, string] => [x, x])]} />
      <Champ label="Famille" name="famille" defaut={lire(p, 'famille')} options={[['', 'Toutes'], ...(d?.options.familles ?? []).map((x): [string, string] => [x, x])]} />
      <Champ label="Article (désignation exacte)" name="article" defaut={lire(p, 'article')} />
    </>,
    visite_client: <>
      <Champ label="Client (code)" name="client" defaut={lire(p, 'client')} placeholder="Rechercher par code ou nom…" liste="clients" />
      <datalist id="clients">
        {(clients?.data ?? []).map((c: any) => <option key={c.ct_num} value={c.ct_num}>{c.ct_intitule}</option>)}
      </datalist>
    </>,
    produits_dormants: <Champ label="Mois d'inactivité" name="mois" type="number" defaut={String(f.mois ?? 6)} />,
    lots_peremption: <Champ label="Jours avant péremption" name="jours" type="number" defaut={String(f.jours ?? 60)} />,
  }

  const exports = d && (
    <>
      <Telecharger className="secondaire contour-accent" href={lien(`${chemin}/export`, p, { format: 'xlsx' })}>Télécharger Excel</Telecharger>
      <Telecharger className="secondaire principal-lien" href={lien(`${chemin}/export`, p, { format: 'pdf' })}>Télécharger PDF</Telecharger>
    </>
  )
  const section = (i: number) => d!.sections[i]
  const tableau = (i: number, cle: string, total?: string) => (
    <TableauSection s={section(i)} p={p} chemin={chemin} cle={cle} totaux={total !== undefined ? d!.totaux : undefined} libelleTotal={total} />
  )

  let blocs: React.ReactNode = null
  if (d) switch (r.nom) {
    case 'chiffre_affaire': {
      const barres = (x: Donnees | null, col: string) => (x?.sections[0].lignes ?? []).slice(0, 8).map((l) => ({
        nom: String(val(x!.sections[0], l, col) ?? '—'), v: val(x!.sections[0], l, 'CA HT'), libelle: pct(val(x!.sections[0], l, '% du CA')),
      }))
      blocs = <div className="grille">
        <Carte titre="Répartition par collaborateur"><Barres items={barres(repCommercial, 'Collaborateur')} /></Carte>
        <Carte titre="Répartition par région" note="code région Sage"><Barres items={barres(repRegion, 'Région')} /></Carte>
        <Carte large titre="Chiffre d'affaire en détail">{tableau(0, 'page', `${entier(d.totaux.nombre)} ${NOMBRE_DE[f.group_by]}`)}</Carte>
      </div>
      break
    }
    case 'comparaison_ca': {
      const s0 = section(0)
      const nomCol = s0.colonnes.find((c) => c.startsWith('Nom')) ?? s0.colonnes[0]
      blocs = <div className="grille">
        <Carte large titre="CA période 1 et période 2 — 6 premières lignes de la période 2">
          <Colonnes legende={{ a: `P1 · ${date(f.date_from_1)} – ${date(f.date_to_1)}`, b: `P2 · ${date(f.date_from_2)} – ${date(f.date_to_2)}` }}
            groupes={s0.lignes.slice(0, 6).map((l) => ({ nom: String(val(s0, l, nomCol)), a: val(s0, l, 'CA Période 1'), b: val(s0, l, 'CA Période 2') }))} />
        </Carte>
        <Carte large titre="Comparaison en détail">{tableau(0, 'page', `${entier(d.totaux.nombre)} lignes`)}</Carte>
      </div>
      break
    }
    case 'balance': {
      const s0 = section(0)
      const mois = s0.colonnes.filter((c) => !['Ref Client', 'Nom Client', 'Commercial', 'A Nouveau', 'Totale'].includes(c))
      blocs = <div className="grille">
        <Carte large titre="Solde restant par mois de facturation" note={`À nouveau (${court(d.totaux['A Nouveau'])}) hors graphique`}>
          <Colonnes legende={{ b: 'Solde TTC restant dû' }} groupes={mois.map((m) => ({ nom: m, b: d.totaux[m] ?? 0 }))} />
        </Carte>
        <Carte large titre="Détail de la balance">{tableau(0, 'page', `${entier(d.totaux.nombre)} clients`)}</Carte>
      </div>
      break
    }
    case 'balance_agee':
      blocs = <div className="grille">
        <Carte large titre="Répartition de l'encours par ancienneté" note={`${mad(d.totaux.Totale)} MAD`}>
          <Pile segments={TRANCHES.map((c, i) => ({ nom: c.replace('j', ' jours'), v: d.totaux[c] ?? 0, couleur: COULEURS_TRANCHES[i], libelle: court(d.totaux[c]) }))} />
        </Carte>
        <Carte large titre="Détail de la balance âgée">{tableau(0, 'page', `${entier(d.totaux.nombre)} clients`)}</Carte>
      </div>
      break
    case 'valeur_stock': {
      const s0 = section(0)
      blocs = <div className="grille">
        <Carte titre="Valeur par dépôt" note="MAD"><Barres items={d.repartition.map((x) => ({ nom: x.libelle, v: x.valeur, libelle: court(x.valeur) }))} /></Carte>
        <Carte titre="Articles les plus valorisés" note="MAD"><Barres items={s0.lignes.slice(0, 6).map((l) => ({
          nom: String(val(s0, l, 'Réf. Article')), v: val(s0, l, 'Valeur Stock'), libelle: court(val(s0, l, 'Valeur Stock')) }))} /></Carte>
        <Carte large titre="Détail — trié par valeur décroissante">{tableau(0, 'page', `${entier(d.totaux.nombre)} lignes`)}</Carte>
      </div>
      break
    }
    case 'visite_client': {
      const s7 = section(6)
      const mois = s7.colonnes.filter((c) => !['Période', 'Total', 'Évolution (%)'].includes(c))
      const [cette, precedente] = s7.lignes
      blocs = <div className="grille">
        {cette && <Carte large titre={`7. Comparaison CA — ${val(s7, cette, 'Période')} vs ${val(s7, precedente, 'Période')}, 6 mois glissants`}>
          <Colonnes legende={{ a: String(val(s7, precedente, 'Période')), b: String(val(s7, cette, 'Période')) }}
            groupes={mois.map((m) => ({ nom: m, a: val(s7, precedente, m) ?? 0, b: val(s7, cette, m) ?? 0 }))} />
        </Carte>}
        {d.sections.slice(0, 6).map((x, i) => (
          <Carte key={x.titre} large={i < 3} titre={x.titre.replace(/^(\d)-/, '$1. ')} note={`${entier(x.lignes.length)} lignes`}>
            {tableau(i, `page${i + 1}`)}
          </Carte>
        ))}
      </div>
      break
    }
    case 'produits_dormants':
      blocs = <div className="grille">
        <Carte large titre="Ancienneté de la dernière vente" note="valeur du stock immobilisée">
          <Barres items={d.repartition.map((x) => ({ nom: x.libelle, v: x.valeur, libelle: `${entier(x.nombre)} produits · ${court(x.valeur)}` }))} />
        </Carte>
        <Carte large titre={section(0).titre}>{tableau(0, 'page')}</Carte>
      </div>
      break
    case 'lots_peremption':
      blocs = section(0).lignes.length
        ? <Carte titre={section(0).titre}>{tableau(0, 'page')}</Carte>
        : <Carte titre={`Lots expirant dans les ${f.jours} prochains jours`}><p className="vide">Aucun lot en péremption détecté.</p></Carte>
      break
    case 'consommation': {
      const [familles, articles] = d.sections
      const top = [...articles.lignes].sort((x, y) => val(articles, y, 'Total Consommation') - val(articles, x, 'Total Consommation')).slice(0, 6)
      blocs = <div className="grille">
        <Carte titre="Récapitulatif par famille" note="unités consommées"><Barres items={familles.lignes.slice(0, 8).map((l) => ({
          nom: String(val(familles, l, 'Famille')), v: val(familles, l, 'Qté Totale Consommée'), libelle: entier(val(familles, l, 'Qté Totale Consommée')) }))} /></Carte>
        <Carte titre="Articles les plus consommés" note="unités sur 6 mois"><Barres items={top.map((l) => ({
          nom: String(val(articles, l, 'Réf. Article')), v: val(articles, l, 'Total Consommation'), libelle: entier(val(articles, l, 'Total Consommation')) }))} /></Carte>
        <Carte large titre="Récapitulatif par famille">{tableau(0, 'page_familles')}</Carte>
        <Carte large titre="Détail par article">{tableau(1, 'page')}</Carte>
      </div>
      break
    }
  }

  return (
    <Page accent={r.couleur}>
      {titre(d?.sous_titre, exports)}
      {champsFiltres[r.nom] && <Filtres bouton={r.nom === 'visite_client' ? 'Générer le rapport' : 'Générer'}>{champsFiltres[r.nom]}</Filtres>}
      {!d ? <Carte><p className="vide">Sélectionnez un client pour générer le rapport.</p></Carte> : <>
        <Kpis accent items={kpis(r.nom, d)} />
        {blocs}
      </>}
    </Page>
  )
}
