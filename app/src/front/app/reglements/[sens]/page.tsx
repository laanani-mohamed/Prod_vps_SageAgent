import { notFound } from 'next/navigation'
import Page from '../../../components/Page'
import { Carte, Champ, Entete, Filtres, Interdit, Kpis, Onglets, Pagination, Tableau } from '../../../components/ui'
import { estCollaborateur, session, vue } from '../../../lib/api'
import { court, date, entier, mad } from '../../../lib/format'
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

  const filtres = {
    domaine: cfg.domaine, piece: lire(p, 'piece'), tiers: lire(p, 'tiers'), intitule: lire(p, 'intitule'),
    date_from: lire(p, 'du') || undefined, date_to: lire(p, 'au') || undefined, page: lire(p, 'page') || 1, taille: 10,
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
        <Champ label="Du (date du document)" name="du" type="date" defaut={lire(p, 'du')} />
        <Champ label="Au" name="au" type="date" defaut={lire(p, 'au')} />
      </Filtres>
      {onglets}
      <Kpis items={[
        { nom: 'Règlements', v: entier(r.kpis.nombre) },
        { nom: 'Montant réglé', v: court(r.kpis.montant), sous: `${mad(r.kpis.montant)} MAD` },
        { nom: cfg.tiers, v: entier(r.kpis.tiers) },
        { nom: 'Dernier règlement', v: date(r.kpis.dernier) },
      ]} />
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
