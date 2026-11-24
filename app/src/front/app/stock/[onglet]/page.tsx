import { notFound } from 'next/navigation'
import Page from '../../../components/Page'
import OngletsStock from '../../../components/OngletsStock'
import Link from 'next/link'
import { Attente } from '../../../components/Interactions'
import { Barres, Carte, Champ, Entete, Filtres, Interdit, Kpis, Pagination, Tableau } from '../../../components/ui'
import { api, estCollaborateur, session, vue } from '../../../lib/api'
import { cellule, court, date, entier, mad, pct } from '../../../lib/format'
import { anneeEnCours, lien, lire, type Params } from '../../../lib/params'

const ONGLETS = { etat: 'État des stocks', entrants: 'Mouvements entrants', sortants: 'Mouvements sortants', alertes: 'Alertes & insights' }
// Même correspondance que la page Streamlit actuelle (alors que Sage nomme 20 « entrée » et 21 « sortie »)
const MOUVEMENTS: Record<string, number> = { entrants: 21, sortants: 20 }
const ALERTES: Record<string, string> = { rupture: 'Rupture de stock', rupture_a: 'Ruptures sur les meilleures ventes', dormant: 'Produits dormants', jamais_vendu: 'Jamais vendus', peremption: 'Lots en péremption' }
const AIDE_ALERTE: Record<string, string> = { rupture: 'article × dépôt à quantité nulle', rupture_a: 'articles des 80 % du CA, sans stock', dormant: 'sans vente depuis N mois', jamais_vendu: 'en stock, aucune vente', peremption: 'lots qui périment bientôt' }
const COULEUR_ALERTE: Record<string, string> = { rupture: '#dc2626', rupture_a: '#9f1239', dormant: '#d97706', jamais_vendu: '#71717a', peremption: '#7c3aed' }
const LIBELLES: Record<string, string> = {
  ar_ref: 'Réf. article', ar_design: 'Désignation', fa_codefamille: 'Famille', de_intitule: 'Dépôt', quantite_totale: 'Quantité',
  derniere_date_vente: 'Dernière vente', nbr_jours_inactif: "Jours d'inactivité", prix_achat: 'Prix achat', valeur_stock: 'Valeur stock',
  ls_noserie: 'N° lot / série', ls_qterestant: 'Qté restante', ls_peremption: 'Péremption', jours_restants: 'Jours restants',
}
const ACCENT = '#f35b04'

export default async function PageStock({ params, searchParams }: { params: Promise<{ onglet: string }>; searchParams: Promise<Params> }) {
  const { onglet } = await params
  if (!(onglet in ONGLETS)) notFound()
  const p = await searchParams
  const s = await session()
  const chemin = `/stock/${onglet}`
  const entete = <Entete titre="Stock & Mouvements" sousTitre="État du stock Sage par article et par dépôt, mouvements et alertes" />
  const onglets = <OngletsStock actif={onglet} />
  if (estCollaborateur(s)) return <Page accent={ACCENT}>{entete}{onglets}<Interdit /></Page>
  const page = lire(p, 'page') || 1

  let contenu: React.ReactNode
  if (onglet === 'etat') {
    const r = await vue('stock_etat', { ref: lire(p, 'ref'), design: lire(p, 'design'), famille: lire(p, 'famille'), page })
    contenu = <>
      <Kpis items={[
        { nom: 'Articles en stock', v: entier(r.kpis.articles), sous: 'quantité > 0' },
        { nom: 'Quantité totale', v: entier(r.kpis.quantite), sous: 'unités, tous dépôts' },
        { nom: 'Valeur du stock', v: court(r.kpis.valeur), sous: `${mad(r.kpis.valeur)} MAD` },
        { nom: 'Dépôts', v: entier(r.kpis.depots) },
      ]} />
      <Carte titre="État actuel des stocks" note="trié par valeur de stock">
        <Filtres cadre={false} colonnes="repeat(3, minmax(0, 1fr)) auto">
          <Champ label="Référence" name="ref" defaut={lire(p, 'ref')} />
          <Champ label="Désignation" name="design" defaut={lire(p, 'design')} />
          <Champ label="Famille" name="famille" defaut={lire(p, 'famille')}
            options={[['', 'Toutes les familles'], ...r.familles.map((f: any): [string, string] => [f.code, `${f.code} · ${f.nom ?? ''}`])]} />
        </Filtres>
        <Tableau
          colonnes={[{ nom: 'Réf. article', largeur: '140px' }, { nom: 'Désignation' }, { nom: 'Code famille', largeur: '120px' }, { nom: 'Dépôt', largeur: '180px' },
            { nom: 'Quantité', droite: true, largeur: '100px' }, { nom: 'Valeur', droite: true, largeur: '120px' }]}
          lignes={r.lignes.map((l: any, i: number) => ({
            cle: `${l.ar_ref}-${l.de_intitule}-${i}`, cellules: [l.ar_ref, l.ar_design, l.fa_codefamille, l.de_intitule, entier(l.as_qtesto), mad(l.as_montsto)],
          }))}
        />
        <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(n) => lien(chemin, p, { page: n })} />
      </Carte>
    </>
  } else if (onglet in MOUVEMENTS) {
    const defaut = anneeEnCours()
    const du = lire(p, 'du') || defaut.debut, au = lire(p, 'au') || defaut.fin
    const r = await vue('documents', { domaine: 2, type: MOUVEMENTS[onglet], date_from: du, date_to: au, page, taille: 10 })
    const choisi = r.lignes.find((l: any) => l.do_piece === lire(p, 'piece_doc')) ?? r.lignes[0]
    const doc = choisi && (await vue('document', { domaine: 2, type: choisi.do_type, piece: choisi.do_piece }))
    contenu = <>
      <Filtres colonnes="minmax(0, 200px) minmax(0, 200px) 1fr max-content">
        <Champ label="Du" name="du" type="date" defaut={du} />
        <Champ label="Au" name="au" type="date" defaut={au} />
        <span />
      </Filtres>
      <Kpis items={[
        { nom: 'Nombre de documents', v: entier(r.kpis.nombre) },
        { nom: `Valeur HT ${onglet === 'entrants' ? 'entrante' : 'sortante'}`, v: `${mad(r.kpis.ht)} MAD` },
      ]} />
      <Carte titre={ONGLETS[onglet as keyof typeof ONGLETS]} note={`documents de stock Sage, type ${MOUVEMENTS[onglet]}`}>
        <Tableau
          colonnes={[{ nom: 'Date', largeur: '110px' }, { nom: 'N° pièce', largeur: '140px' }, { nom: 'Dépôt' }, { nom: 'Montant HT', droite: true, largeur: '140px' }]}
          lignes={r.lignes.map((l: any) => ({
            cle: l.do_piece, actif: l === choisi, href: lien(chemin, p, { piece_doc: l.do_piece }),
            cellules: [date(l.date), l.do_piece, l.ct_intitule ? `${l.ct_intitule} (${l.do_tiers})` : l.do_tiers, mad(l.do_totalht)],
          }))}
          vide="Aucun mouvement sur la période."
        />
        <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(n) => lien(chemin, p, { page: n })} />
      </Carte>
      {doc && (
        <Carte titre={`Lignes du document ${doc.entete.piece}`} note={`${doc.entete.intitule ?? doc.entete.tiers} · ${date(doc.entete.date)} · ${doc.total} ligne(s)`}>
          <Tableau
            colonnes={[{ nom: 'Réf. article', largeur: '130px' }, { nom: 'Désignation' }, { nom: 'Qté', droite: true, largeur: '70px' },
              { nom: 'PU HT', droite: true, largeur: '110px' }, { nom: 'Montant HT', droite: true, largeur: '130px' }]}
            lignes={doc.lignes.map((l: any, i: number) => ({
              cle: String(i), cellules: [l.ar_ref ?? '—', l.dl_design, entier(l.dl_qte), mad(l.dl_prixunitaire), mad(l.dl_montantht)],
            }))}
          />
        </Carte>
      )}
    </>
  } else {
    const type = lire(p, 'type') || 'rupture'
    const defaut = anneeEnCours()   // meilleures ventes : CA du 01/01 à aujourd'hui, comme le Tableau de Bord
    const du = lire(p, 'du') || defaut.debut, au = lire(p, 'au') || defaut.fin
    const estRv = type === 'rupture_a'
    const [r, rv, familles] = await Promise.all([
      vue('stock_alertes', { type: estRv ? 'rupture' : type, mois: lire(p, 'mois') || 6, jours: lire(p, 'jours') || 60, famille: lire(p, 'famille'), page: estRv ? 1 : page }),
      vue('ruptures_ventes', { date_from: du, date_to: au, famille: lire(p, 'famille'), page: estRv ? page : 1 }),
      api('/api/referentiel/familles', { client_schema: s.client }),
    ])
    const types = [...r.types.slice(0, 1), { type: 'rupture_a', nombre: rv?.total ?? 0 }, ...r.types.slice(1)]
    const courant = estRv ? 'rupture_a' : r.type
    const nomFamille = Object.fromEntries((familles?.data ?? []).map((f: any) => [f.fa_codefamille, f.fa_intitule]))
    const colonnes = r.colonnes.filter((c: string) => c !== 'prix_achat') // tableau sur 2/3 de la largeur
    const format = (c: string, v: unknown) => (c.includes('date') || c === 'ls_peremption' ? date(v as string) : cellule(v))
    contenu = <>
      <nav className="types-alertes" aria-label="Type d'alerte">
        {types.map((t: any) => (
          <Link prefetch={false} key={t.type} href={lien(chemin, {}, { type: t.type })} className="type-alerte" aria-current={t.type === courant ? 'page' : undefined}>
            <span className="nom"><i style={{ background: COULEUR_ALERTE[t.type] }} />{ALERTES[t.type]}</span>
            <strong>{entier(t.nombre)}</strong>
            <span className="doux petit">{AIDE_ALERTE[t.type]}<Attente /></span>
          </Link>
        ))}
      </nav>
      <Filtres colonnes={estRv ? 'minmax(0, 260px) minmax(0, 200px) minmax(0, 200px) 1fr max-content' : 'minmax(0, 260px) minmax(0, 220px) 1fr max-content'}>
        <input type="hidden" name="type" value={type} />
        <Champ label="Famille" name="famille" defaut={lire(p, 'famille')}
          options={[['', 'Toutes les familles'], ...(familles?.data ?? []).map((f: any): [string, string] => [f.fa_codefamille, `${f.fa_codefamille} · ${f.fa_intitule ?? ''}`])]} />
        {type === 'dormant' && <Champ label="Mois d'inactivité" name="mois" type="number" defaut={String(r.mois)} />}
        {type === 'peremption' && <Champ label="Jours avant péremption" name="jours" type="number" defaut={String(r.jours)} />}
        {estRv && <><Champ label="Du" name="du" type="date" defaut={du} /><Champ label="Au" name="au" type="date" defaut={au} /></>}
        {type !== 'dormant' && type !== 'peremption' && !estRv && <span />}
        <span />
      </Filtres>
      {estRv ? <RupturesVentes rv={rv} nomFamille={nomFamille} pagination={(n) => lien(chemin, p, { page: n })} /> : r.total === 0 ? (
        <Carte titre={ALERTES[r.type]}>
          <p className="vide">{r.type === 'peremption'
            ? `Aucun lot ne périme dans les ${r.jours} prochains jours. La table des lots (F_LOTSERIE) est presque vide : le suivi par lot n'est pas utilisé dans Sage.`
            : 'Aucun produit concerné.'}</p>
        </Carte>
      ) : <div className="grille-3">
        <Carte titre="Produits concernés par famille" note="10 premières familles">
          <Barres items={r.par_famille.map((x: any) => ({ nom: `${x.famille} · ${nomFamille[x.famille] ?? ''}`, v: x.nombre, libelle: entier(x.nombre) }))} />
        </Carte>
        <Carte span={2} titre={ALERTES[r.type]} note={`${entier(r.total)} lignes`}>
          <Tableau
            colonnes={colonnes.map((c: string) => ({ nom: LIBELLES[c] ?? c, droite: ['quantite_totale', 'prix_achat', 'valeur_stock', 'nbr_jours_inactif', 'ls_qterestant', 'jours_restants'].includes(c) }))}
            lignes={r.lignes.map((l: any, i: number) => ({ cle: String(i), cellules: colonnes.map((c: string) => format(c, l[c])) }))}
          />
          <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(n) => lien(chemin, p, { page: n })} />
        </Carte>
      </div>}
    </>
  }

  return <Page accent={ACCENT}>{entete}{onglets}{contenu}</Page>
}

/** Alerte « Ruptures sur les meilleures ventes » (vue ruptures_ventes) : articles qui font 80 % du CA HT de la période, sans stock. */
function RupturesVentes({ rv, nomFamille, pagination }: { rv: any; nomFamille: Record<string, string>; pagination: (n: number) => string }) {
  if (!rv) return <p className="vide">Alerte indisponible.</p>
  if (!rv.total) return <Carte titre={ALERTES.rupture_a}><p className="vide">Aucune des meilleures ventes n&apos;est en rupture.</p></Carte>
  const periode = `du ${date(rv.du)} au ${date(rv.au)}`, an = rv.au.slice(0, 4)
  const maxCa = Math.max(rv.ca_max, 1)   // échelle commune à toutes les pages : le plus gros CA en rupture
  return <>
    <Kpis items={[
      { nom: 'Meilleures ventes en rupture', v: <AvecCercle valeur={entier(rv.total)} part={(rv.total / rv.classe_a) * 100} classe="mauvais" />, ton: 'mauvais',
        sous: `sur ${entier(rv.classe_a)} articles qui font 80 % du CA` },
      { nom: `CA ${an} concerné`, v: <AvecCercle valeur={court(rv.ca_ruptures)} part={rv.ca_total ? (rv.ca_ruptures / rv.ca_total) * 100 : 0} />, sous: `du CA HT ${periode}` },
      { nom: 'Ventes à risque par mois', v: court((rv.ca_ruptures / rv.jours) * 365.25 / 12), sous: `CA moyen par mois depuis le ${date(rv.du)}, tant que la rupture dure` },
      { nom: 'Fournisseurs à relancer', v: entier(rv.fournisseurs), sous: 'dernier fournisseur de chaque article' },
    ]} />
    <div className="grille">
      <Carte titre="Ruptures par fournisseur" note={`10 premiers · CA ${an} des articles en rupture`}>
        <Barres items={rv.par_fournisseur.map((x: any) => ({ nom: x.nom, v: x.ca, libelle: `${court(x.ca)} · ${entier(x.nombre)} art.` }))} />
      </Carte>
      <Carte titre="Produits concernés par famille" note="10 premières familles">
        <Barres items={rv.par_famille.map((x: any) => ({ nom: `${x.famille} · ${nomFamille[x.famille] ?? ''}`, v: x.nombre, libelle: entier(x.nombre) }))} />
      </Carte>
    </div>
    <Carte titre={ALERTES.rupture_a} note={`${entier(rv.total)} articles · classés par CA HT ${periode}`}>
      <p className="doux petit">Rang = place de l&apos;article dans le classement des ventes de la période (1 = plus gros CA). Le dernier fournisseur est celui de la dernière facture d&apos;achat.</p>
      <Tableau
        colonnes={[{ nom: 'Rang', largeur: '64px' }, { nom: 'Réf. article', largeur: '130px' }, { nom: 'Désignation' }, { nom: `CA ${an}`, droite: true, largeur: '180px' },
          { nom: 'Qté vendue', droite: true, largeur: '96px' }, { nom: 'Dernière vente', largeur: '110px' }, { nom: 'Stock', droite: true, largeur: '70px' }, { nom: 'Dernier fournisseur', largeur: '230px' }]}
        lignes={rv.lignes.map((l: any) => ({
          cle: l.ar_ref,
          cellules: [<span key="r" className="doux fort">#{l.rang}</span>, <strong key="a">{l.ar_ref}</strong>, l.ar_design,
            <span key="c" className="part"><span className="piste"><span style={{ width: `${Math.max(2, (l.ca / maxCa) * 100)}%` }} /></span>{court(l.ca)}</span>,
            entier(l.qte), date(l.derniere_vente), <strong key="s" className="mauvais">{entier(l.stock)}</strong>,
            `${l.fournisseur}${l.dernier_achat ? ` · ${date(l.dernier_achat)}` : ''}`],
        }))}
      />
      <Pagination total={rv.total} page={rv.page} taille={rv.taille_page} href={pagination} />
    </Carte>
  </>
}

/** Valeur d'un KPI avec, à droite, un cercle de pourcentage (part du total). */
function AvecCercle({ valeur, part, classe }: { valeur: string; part: number; classe?: string }) {
  const p = Math.min(100, Math.max(0, part))
  return (
    <span className="kpi-cercle">
      <span>{valeur}</span>
      <span className={['cercle-kpi', classe].filter(Boolean).join(' ')} role="img" aria-label={`${pct(part)} du total`}>
        <svg viewBox="0 0 64 64" aria-hidden="true">
          <circle cx="32" cy="32" r="26" className="piste-anneau" />
          <circle cx="32" cy="32" r="26" pathLength={100} className="valeur-anneau" strokeDasharray={`${p} 100`} transform="rotate(-90 32 32)" />
        </svg>
        <span>{pct(part)}</span>
      </span>
    </span>
  )
}
