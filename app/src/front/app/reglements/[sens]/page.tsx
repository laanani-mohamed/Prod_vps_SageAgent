import { notFound } from 'next/navigation'
import Page from '../../../components/Page'
import { Barres, Carte, Champ, Entete, Filtres, Interdit, Onglets, Pagination, Tableau } from '../../../components/ui'
import { estCollaborateur, session, vue } from '../../../lib/api'
import { court, date, entier, mad, pct } from '../../../lib/format'
import { lien, lire, type Params } from '../../../lib/params'

const SENS = {
  encaissements: { domaine: 0, onglet: 'Encaissements clients (ventes)', code: 'Code client', tiers: 'Clients concernés', titre: 'Historique des encaissements' },
  decaissements: { domaine: 1, onglet: 'Décaissements fournisseurs (achats)', code: 'Code fourn.', tiers: 'Fournisseurs concernés', titre: 'Historique des décaissements' },
} as const

export default async function PageReglements({ params, searchParams }: { params: Promise<{ sens: string }>; searchParams: Promise<Params> }) {
  const { sens } = await params
  if (!(sens in SENS)) notFound()
  const cfg = SENS[sens as keyof typeof SENS]
  const p = await searchParams
  const collab = estCollaborateur(await session())
  const chemin = `/reglements/${sens}`

  const onglets = (
    <Onglets items={Object.entries(SENS).map(([cle, x]) => ({
      nom: x.onglet, href: `/reglements/${cle}`, actif: cle === sens, interdit: collab && x.domaine === 1,
    }))} />
  )
  const entete = <Entete titre="Règlements & Flux Financiers" sousTitre="Encaissements clients et décaissements fournisseurs (Sage F_REGLECH)" />
  if (collab && cfg.domaine === 1) return <Page accent="#00b4d8">{entete}{onglets}<Interdit /></Page>

  // Période par défaut : de la plus ancienne à la plus récente facture (bornes renvoyées par la vue recouvrement, affichées dans les filtres)
  const rec = await vue('recouvrement', { domaine: cfg.domaine, date_from: lire(p, 'du') || undefined, date_to: lire(p, 'au') || undefined })
  const du = lire(p, 'du') || rec?.du, au = lire(p, 'au') || rec?.au
  const filtres = {
    domaine: cfg.domaine, piece: lire(p, 'piece'), tiers: lire(p, 'tiers'), intitule: lire(p, 'intitule'),
    date_from: du, date_to: au, page: lire(p, 'page') || 1, taille: 10,
  }
  const r = await vue('reglements', filtres)
  // Règlement choisi (par défaut le plus récent) et document associé
  const choisi = r.lignes.find((l: any) => String(l.rg_no) === lire(p, 'rg') && l.do_piece === lire(p, 'piece_doc')) ?? r.lignes[0]
  const doc = choisi && (await vue('document', { domaine: choisi.do_domaine, type: choisi.do_type, piece: choisi.do_piece }))

  return (
    <Page accent="#00b4d8">
      {entete}
      <Filtres titre="Filtres de recherche" colonnes="repeat(3, minmax(0, 1fr)) minmax(0, 170px) minmax(0, 170px) auto" bouton="Appliquer les filtres">
        <Champ label="N° pièce" name="piece" defaut={filtres.piece} placeholder="ex : 26FA02183" />
        <Champ label="Code tiers" name="tiers" defaut={filtres.tiers} placeholder="client ou fournisseur" />
        <Champ label="Raison sociale" name="intitule" defaut={filtres.intitule} placeholder="ex : ZIRAOUI" />
        <Champ label="Du (date du document)" name="du" type="date" defaut={du} />
        <Champ label="Au" name="au" type="date" defaut={au} />
      </Filtres>
      {onglets}
      <Recouvrement rec={rec} clients={cfg.domaine === 0} />
      <Carte titre={cfg.titre} note="Cliquez sur un règlement pour voir les lignes du document associé">
        <Tableau
          colonnes={[{ nom: 'Réf. règl.', largeur: '96px' }, { nom: 'N° pièce', largeur: '116px' }, { nom: 'Date', largeur: '104px' }, { nom: cfg.code, largeur: '100px' },
            { nom: 'Raison sociale' }, { nom: 'ICE', largeur: '150px' }, { nom: 'Type', largeur: '110px' }, { nom: 'Montant', droite: true, largeur: '120px' }]}
          lignes={r.lignes.map((l: any) => ({
            cle: `${l.rg_no}-${l.do_piece}`, actif: l === choisi,
            href: lien(chemin, p, { rg: l.rg_no, piece_doc: l.do_piece }),
            cellules: [l.rg_no, l.do_piece, date(l.date), l.do_tiers, l.ct_intitule, l.ice || '—', <span key="t" className="puce">{l.type}</span>,
              <span key="m" className={l.rc_montant < 0 ? 'mauvais fort' : 'fort'}>{mad(l.rc_montant)}</span>],
          }))}
          vide="Aucun règlement pour ces filtres."
        />
        <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(n) => lien(chemin, p, { page: n })} />
      </Carte>
      {doc && (
        <Carte>
          <div className="entete-detail">
            <div>
              <div className="sous-titre accent-texte">Détail du document associé</div>
              <h2>{doc.entete.piece} · {doc.entete.intitule ?? doc.entete.tiers}</h2>
              <p className="doux petit">{doc.entete.type} du {date(doc.entete.date)}</p>
            </div>
            <div className="droite"><div className="doux petit">Montant réglé</div><div className="grand-moyen fort">{mad(choisi.rc_montant)} DH</div></div>
          </div>
          <div className="carte-titre"><h3>Lignes du document</h3><span className="doux petit">{entier(doc.lignes.length)} sur {entier(doc.total)} lignes</span></div>
          <Tableau
            colonnes={[{ nom: 'Réf. article', largeur: '130px' }, { nom: 'Désignation' }, { nom: 'Qté', droite: true, largeur: '70px' },
              { nom: 'PU HT', droite: true, largeur: '110px' }, { nom: 'Montant HT', droite: true, largeur: '120px' }, { nom: 'Montant TTC', droite: true, largeur: '120px' }]}
            lignes={doc.lignes.map((l: any, i: number) => ({
              cle: String(i), cellules: [l.ar_ref ?? '—', l.dl_design, entier(l.dl_qte), mad(l.dl_prixunitaire), mad(l.dl_montantht), mad(l.dl_montantttc)],
            }))}
          />
        </Carte>
      )}
    </Page>
  )
}

// ---------------------------------------------------------------------------------------------------------------
// Recouvrement des factures de la période (vue recouvrement) : encaissé, reste à encaisser, ancienneté, état
// ---------------------------------------------------------------------------------------------------------------
const VERT = '#a5be00', ORANGE = '#ff9f1c', ROUGE = '#f34213'
const COUL_AGE = [VERT, ORANGE, '#f9711a', ROUGE], COUL_ETAT = [VERT, ORANGE, ROUGE]   // 61-90 j : entre l'orange et le rouge

/** Anneau à segments (parts en %), valeur au centre. */
function Anneau({ segments, centre, sousCentre, aria, arrondi }: { segments: { part: number; couleur: string }[]; centre: string; sousCentre: string; aria: string; arrondi?: boolean }) {
  let avant = 0
  return (
    <div className="anneau-rec">
      <svg viewBox="0 0 120 120" role="img" aria-label={aria}>
        <circle cx="60" cy="60" r="48" className="piste-anneau" />
        {segments.map((g, i) => {
          const c = <circle key={i} cx="60" cy="60" r="48" pathLength={100} stroke={g.couleur} strokeLinecap={arrondi ? 'round' : 'butt'}
            strokeDasharray={`${g.part.toFixed(3)} ${(100 - g.part).toFixed(3)}`} strokeDashoffset={(-avant).toFixed(3)} transform="rotate(-90 60 60)" />
          avant += g.part
          return c
        })}
      </svg>
      <span><strong>{centre}</strong><span>{sousCentre}</span></span>
    </div>
  )
}

function Ligne({ couleur, nom, sous, v, rouge }: { couleur: string; nom: string; sous: string; v: string; rouge?: boolean }) {
  return <div className="ligne-rec"><i style={{ background: couleur }} /><span><strong>{nom}</strong><span className="doux petit">{sous}</span></span><strong style={rouge ? { color: ROUGE } : undefined}>{v}</strong></div>
}

function Recouvrement({ rec, clients }: { rec: any; clients: boolean }) {
  if (!rec) return null
  const per = `factures du ${date(rec.du)} au ${date(rec.au)}`
  if (!clients && !rec.regle) return (
    <Carte titre="Recouvrement des factures fournisseurs" note={per}>
      <p className="vide">Non disponible : sur les {entier(rec.factures)} factures d&apos;achat de la période, Sage n&apos;enregistre aucun montant réglé dans ces données (les paiements fournisseurs ne sont pas saisis sur les factures).</p>
    </Carte>
  )
  if (!rec.factures) return <Carte titre="Recouvrement" note={per}><p className="vide">Aucune facture sur la période.</p></Carte>
  const taux = rec.ttc ? (1 - rec.reste / rec.ttc) * 100 : 0
  const plus90 = rec.tranches[3], nonSoldees = rec.etat[1].nombre + rec.etat[2].nombre
  const verbe = clients ? 'encaiss' : 'pay'
  return (
    <div className="grille grille-rec">
      <Carte titre={clients ? 'Encaissé' : 'Payé'} note={per}>
        <div className="zone-anneau">
          <Anneau segments={[{ part: Math.min(100, Math.max(0, taux)), couleur: 'var(--accent)' }]} arrondi centre={pct(taux)} sousCentre={`du TTC ${verbe}é`} aria={`Taux de recouvrement : ${pct(taux)}`} />
          <div className="lignes-rec">
            <Ligne couleur="var(--accent)" nom={clients ? 'Encaissé' : 'Payé'} sous="TTC, avoirs déduits" v={court(rec.ttc - rec.reste)} />
            <Ligne couleur="var(--gris)" nom="Facturé" sous={`${entier(rec.factures)} factures`} v={court(rec.ttc)} />
          </div>
        </div>
      </Carte>
      <Carte titre={clients ? 'Reste à encaisser' : 'Reste à payer'} note={clients ? 'même chiffre que la page Ventes' : 'même chiffre que la page Achats'}>
        <div className="reste-rec">
          <div className="reste-haut"><strong>{court(rec.reste)}</strong><span className="doux petit">{pct(100 - taux)} du montant facturé TTC</span></div>
          <div className="barre-rec" role="img" aria-label={`Reste : ${pct(100 - taux)} du montant facturé`}>
            <span style={{ width: `${Math.max(0, taux)}%`, background: 'var(--accent)' }} /><span style={{ width: `${Math.max(0, 100 - taux)}%`, background: ROUGE }} />
          </div>
          <div className="legende-rec doux petit"><span><i style={{ background: 'var(--accent)' }} />{verbe}é {pct(taux)}</span><span><i style={{ background: ROUGE }} />reste {pct(100 - taux)}</span></div>
          <div className="minis-rec">
            <div><span className="doux">Factures non soldées</span><strong>{entier(nonSoldees)}</strong><span className="doux petit">dont {entier(rec.etat[1].nombre)} partiellement réglées</span></div>
            <div><span className="doux">Impayés de plus de 90 jours</span><strong style={{ color: ROUGE }}>{court(plus90.montant)}</strong>
              <span className="doux petit">{pct(rec.reste_factures ? (plus90.montant / rec.reste_factures) * 100 : null)} du reste dû · {entier(plus90.nombre)} factures</span></div>
          </div>
        </div>
      </Carte>
      <Carte titre={clients ? 'Ancienneté du reste à encaisser' : 'Ancienneté du reste à payer'} note="jours depuis la date de facture">
        <Barres items={rec.tranches.map((t: any, i: number) => ({ nom: t.nom, v: t.montant, libelle: `${court(t.montant)} · ${entier(t.nombre)} fact.`, couleur: COUL_AGE[i] }))} />
        <p className="doux petit">Sage n&apos;exporte pas les dates d&apos;échéance : l&apos;âge part de la date de facture. Montants avant imputation de {court(rec.avoirs)} d&apos;avoirs.</p>
      </Carte>
      <Carte titre="État des factures" note={`${entier(rec.factures)} factures`}>
        <div className="zone-anneau">
          <Anneau segments={rec.etat.map((e: any, i: number) => ({ part: (e.nombre / rec.factures) * 100, couleur: COUL_ETAT[i] }))} centre={entier(rec.factures)} sousCentre="factures"
            aria={rec.etat.map((e: any) => `${e.nom} : ${entier(e.nombre)}`).join(', ')} />
          <div className="lignes-rec">
            {rec.etat.map((e: any, i: number) => (
              <Ligne key={e.nom} couleur={COUL_ETAT[i]} nom={e.nom} sous={`${i === 0 ? 'TTC' : 'reste dû'} ${court(e.montant)}`} v={`${entier(e.nombre)} · ${pct((e.nombre / rec.factures) * 100)}`} rouge={i === 2} />
            ))}
          </div>
        </div>
      </Carte>
    </div>
  )
}
