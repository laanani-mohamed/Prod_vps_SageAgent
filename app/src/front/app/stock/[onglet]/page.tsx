import { notFound } from 'next/navigation'
import Page from '../../../components/Page'
import OngletsStock from '../../../components/OngletsStock'
import Link from 'next/link'
import { Attente } from '../../../components/Interactions'
import { Barres, Carte, Champ, Entete, Filtres, Interdit, Kpis, Pagination, Tableau } from '../../../components/ui'
import { api, estCollaborateur, session, vue } from '../../../lib/api'
import { cellule, court, date, entier, mad } from '../../../lib/format'
import { anneeEnCours, lien, lire, type Params } from '../../../lib/params'

const ONGLETS = { etat: 'État des stocks', entrants: 'Mouvements entrants', sortants: 'Mouvements sortants', alertes: 'Alertes & insights' }
// Même correspondance que la page Streamlit actuelle (alors que Sage nomme 20 « entrée » et 21 « sortie »)
const MOUVEMENTS: Record<string, number> = { entrants: 21, sortants: 20 }
const ALERTES: Record<string, string> = { rupture: 'Rupture de stock', dormant: 'Produits dormants', jamais_vendu: 'Jamais vendus', peremption: 'Lots en péremption' }
const AIDE_ALERTE: Record<string, string> = { rupture: 'article × dépôt à quantité nulle', dormant: 'sans vente depuis N mois', jamais_vendu: 'en stock, aucune vente', peremption: 'lots qui périment bientôt' }
const COULEUR_ALERTE: Record<string, string> = { rupture: '#dc2626', dormant: '#d97706', jamais_vendu: '#71717a', peremption: '#7c3aed' }
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
        { nom: `Valeur HT ${onglet === 'entrants' ? 'entrante' : 'sortante'}`, v: `${mad(r.kpis.ht)} DH` },
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
    const [r, familles] = await Promise.all([
      vue('stock_alertes', { type, mois: lire(p, 'mois') || 6, jours: lire(p, 'jours') || 60, famille: lire(p, 'famille'), page }),
      api('/api/referentiel/familles', { client_schema: s.client }),
    ])
    const nomFamille = Object.fromEntries((familles?.data ?? []).map((f: any) => [f.fa_codefamille, f.fa_intitule]))
    const colonnes = r.colonnes.filter((c: string) => c !== 'prix_achat') // tableau sur 2/3 de la largeur
    const format = (c: string, v: unknown) => (c.includes('date') || c === 'ls_peremption' ? date(v as string) : cellule(v))
    contenu = <>
      <nav className="types-alertes" aria-label="Type d'alerte">
        {r.types.map((t: any) => (
          <Link prefetch={false} key={t.type} href={lien(chemin, {}, { type: t.type })} className="type-alerte" aria-current={t.type === r.type ? 'page' : undefined}>
            <span className="nom"><i style={{ background: COULEUR_ALERTE[t.type] }} />{ALERTES[t.type]}</span>
            <strong>{entier(t.nombre)}</strong>
            <span className="doux petit">{AIDE_ALERTE[t.type]}<Attente /></span>
          </Link>
        ))}
      </nav>
      <Filtres colonnes="minmax(0, 260px) minmax(0, 220px) 1fr max-content">
        <input type="hidden" name="type" value={type} />
        <Champ label="Famille" name="famille" defaut={lire(p, 'famille')}
          options={[['', 'Toutes les familles'], ...(familles?.data ?? []).map((f: any): [string, string] => [f.fa_codefamille, `${f.fa_codefamille} · ${f.fa_intitule ?? ''}`])]} />
        {type === 'dormant' && <Champ label="Mois d'inactivité" name="mois" type="number" defaut={String(r.mois)} />}
        {type === 'peremption' && <Champ label="Jours avant péremption" name="jours" type="number" defaut={String(r.jours)} />}
        {type !== 'dormant' && type !== 'peremption' && <span />}
        <span />
      </Filtres>
      {r.total === 0 ? (
        <Carte titre={ALERTES[r.type]}>
          <p className="vide">{r.type === 'peremption'
            ? `Aucun lot ne périme dans les ${r.jours} prochains jours. La table des lots (F_LOTSERIE) est presque vide : le suivi par lot n'est pas utilisé dans Sage.`
            : 'Aucun produit concerné.'}</p>
        </Carte>
      ) : <div className="grille-3">
        <Carte titre="Produits concernés par famille" note="5 premières familles">
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
