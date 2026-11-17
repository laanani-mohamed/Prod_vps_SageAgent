import { api, estCollaborateur, session, vue } from '../lib/api'
import { court, date, entier, mad, optionsCommerciaux } from '../lib/format'
import { anneeEnCours, lien, lire, type Params } from '../lib/params'
import Page from './Page'
import { Carte, Champ, Entete, Filtres, Interdit, Kpis, Onglets, Pagination, Puce, Tableau } from './ui'

const DOMAINES = {
  0: { titre: 'Gestion des Ventes', sous: 'Documents de vente Sage : devis, commandes, livraisons, factures', code: 'Code client', intitule: 'Intitulé client', tiers: 'Client' },
  1: { titre: 'Gestion des Achats', sous: "Documents d'achat Sage : demandes, commandes, livraisons, factures", code: 'Code fournisseur', intitule: 'Intitulé fournisseur', tiers: 'Fournisseur' },
}
const TON = { 'Réglée': 'bon', 'Non réglée': 'mauvais' } as const

/** Page Gestion des Ventes (domaine 0) ou des Achats (domaine 1). */
export default async function Documents({ domaine, p, chemin }: { domaine: 0 | 1; p: Params; chemin: string }) {
  const cfg = DOMAINES[domaine]
  const s = await session()
  const collab = estCollaborateur(s)
  const entete = <Entete titre={cfg.titre} sousTitre={cfg.sous} />
  if (collab && domaine === 1) return <Page theme="emeraude">{entete}<Interdit /></Page>

  const defaut = anneeEnCours()
  const filtres = {
    domaine, piece: lire(p, 'piece'), tiers: lire(p, 'tiers'), intitule: lire(p, 'intitule'),
    date_from: lire(p, 'du') || defaut.debut, date_to: lire(p, 'au') || defaut.fin,
    non_regles: lire(p, 'non_regles') === '1', type: lire(p, 'type') || undefined, page: lire(p, 'page') || 1, taille: 10,
  }
  const [r, collaborateurs] = await Promise.all([
    vue('documents', filtres, lire(p, 'commercial') ? [Number(lire(p, 'commercial'))] : []),
    collab ? null : api('/api/referentiel/collaborateurs', { client_schema: s.client }),
  ])
  // Document choisi (par défaut le plus récent du type affiché) : entête et lignes
  const choisi = r.lignes.find((l: any) => l.do_piece === lire(p, 'piece_doc')) ?? r.lignes[0]
  const doc = choisi && (await vue('document', { domaine, type: choisi.do_type, piece: choisi.do_piece }))

  return (
    <Page theme="emeraude">
      {entete}
      <Filtres titre="Filtres de recherche" note="les filtres s'appliquent à tous les types de documents" colonnes="repeat(4, minmax(0, 1fr))"
        bouton="Appliquer les filtres" suite={<>
          <Champ label="Du" name="du" type="date" defaut={filtres.date_from} />
          <Champ label="Au" name="au" type="date" defaut={filtres.date_to} />
          <label className="case"><input type="checkbox" name="non_regles" value="1" defaultChecked={filtres.non_regles} />Non réglés uniquement (reste &gt; 0)</label>
        </>}>
        <Champ label="N° pièce" name="piece" defaut={filtres.piece} />
        <Champ label={cfg.code} name="tiers" defaut={filtres.tiers} />
        <Champ label={cfg.intitule} name="intitule" defaut={filtres.intitule} />
        {collab ? <span /> : <Champ label="Commercial" name="commercial" defaut={lire(p, 'commercial')} options={optionsCommerciaux(collaborateurs)} />}
      </Filtres>
      <Kpis items={[
        { nom: 'Factures de la période', v: entier(r.kpis.nombre) },
        { nom: 'Montant HT', v: court(r.kpis.ht), sous: mad(r.kpis.ht) },
        { nom: 'Montant TTC', v: court(r.kpis.ttc), sous: mad(r.kpis.ttc) },
        { nom: 'Reste à payer', v: court(r.kpis.reste), sous: mad(r.kpis.reste), ton: r.kpis.reste > 0 ? 'mauvais' : undefined },
      ]} />
      <Carte>
        <Onglets pleineLargeur items={r.types.map((t: any) => ({
          nom: t.nom, nombre: t.nombre, actif: t.type === r.type, href: lien(chemin, p, { type: t.type, page: undefined, piece_doc: undefined }),
        }))} />
        <div className="carte-titre doux petit">
          <span>Cliquez sur une ligne pour afficher les détails du document</span>
          <span>{entier(r.lignes.length)} sur {entier(r.total)} documents</span>
        </div>
        <Tableau
          colonnes={[{ nom: 'N° pièce', largeur: '116px' }, { nom: 'Date', largeur: '100px' }, { nom: 'Commercial', largeur: '150px' }, { nom: cfg.code, largeur: '130px' },
            { nom: cfg.tiers }, { nom: 'Montant HT', droite: true, largeur: '116px' }, { nom: 'TVA', droite: true, largeur: '100px' },
            { nom: 'TTC', droite: true, largeur: '116px' }, { nom: 'Reste à payer', droite: true, largeur: '116px' }]}
          lignes={r.lignes.map((l: any) => ({
            cle: l.do_piece, actif: l === choisi, href: lien(chemin, p, { piece_doc: l.do_piece }),
            cellules: [l.do_piece, date(l.date), l.commercial, l.do_tiers, l.ct_intitule, mad(l.do_totalht), mad(l.tva), mad(l.do_totalttc),
              <span key="r" className={l.reste_a_payer > 0 ? 'mauvais fort' : undefined}>{mad(l.reste_a_payer)}</span>],
          }))}
          vide="Aucun document pour ces filtres."
        />
        <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(n) => lien(chemin, p, { page: n })} />
      </Carte>
      {doc && (
        <Carte>
          <div className="entete-detail">
            <div>
              <div className="sous-titre">Détails de la pièce</div>
              <h2>{doc.entete.piece} · {doc.entete.intitule ?? ''}</h2>
              <p className="doux petit">{cfg.tiers} {doc.entete.tiers} · {doc.entete.type} du {date(doc.entete.date)} · Commercial {doc.entete.commercial}</p>
            </div>
            {doc.entete.statut && <Puce ton={TON[doc.entete.statut as keyof typeof TON]}>{doc.entete.statut}</Puce>}
          </div>
          <Kpis items={[
            { nom: 'Montant HT', v: mad(doc.entete.ht) }, { nom: 'TVA', v: mad(doc.entete.tva) },
            { nom: 'Montant TTC', v: mad(doc.entete.ttc) }, { nom: 'Reste à payer', v: mad(doc.entete.reste), ton: doc.entete.reste > 0 ? 'mauvais' : undefined },
          ]} />
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
