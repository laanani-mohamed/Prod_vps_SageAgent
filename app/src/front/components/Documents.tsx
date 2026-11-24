import { api, estCollaborateur, session, vue } from '../lib/api'
import { date, entier, mad, montant, optionsCommerciaux } from '../lib/format'
import { anneeEnCours, lien, lire, type Params } from '../lib/params'
import { AnalyseAchats, AnalyseVentes } from './Analyse'
import Page from './Page'
import { FormulaireGet } from './Interactions'
import { Carte, Entete, Interdit, Kpis, Onglets, Pagination, Periode, Puce, Tableau } from './ui'

const DOMAINES = {
  0: { titre: 'Gestion des Ventes', sous: 'Documents de vente Sage : devis, commandes, livraisons, factures', code: 'Code client', intitule: 'Intitulé client', tiers: 'Client',
       exPiece: 'ex : 26FA02197', exCode: 'ex : C0015', exIntitule: 'ex : EQUIP AUTO GHARB' },
  1: { titre: 'Gestion des Achats', sous: "Documents d'achat Sage : demandes, commandes, livraisons, factures", code: 'Code fournisseur', intitule: 'Intitulé fournisseur', tiers: 'Fournisseur',
       exPiece: 'ex : 26109763', exCode: 'ex : F180005', exIntitule: 'ex : CAPRAM' },
}
const TON = { 'Réglée': 'bon', 'Non réglée': 'mauvais' } as const

/** Résumé des factures de la période (maquettes) : grand montant (HT en vente, TTC en achat) et reste dû avec sa part du TTC. */
function Resume({ domaine, k, du, au }: { domaine: 0 | 1; k: { nombre: number; ht: number; ttc: number; reste: number }; du: string; au: string }) {
  const vente = domaine === 0
  const part = k.ttc > 0 ? (k.reste / k.ttc) * 100 : 0
  const ytd = du.slice(5) === '01-01' && du.slice(0, 4) === au.slice(0, 4)
  const centre = Math.abs(part - Math.round(part)) < 0.05 ? `${Math.round(part)} %` : `${part.toLocaleString('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} %`
  return (
    <div className="resume">
      <section className="carte resume-principal" aria-labelledby="resume-montant">
        <div className="carte-titre"><h2 id="resume-montant" className="doux moyen">Montant facturé {vente ? 'HT' : 'TTC'}</h2>
          <Puce>Factures · {ytd ? `YTD ${au.slice(0, 4)}` : `du ${date(du)} au ${date(au)}`}</Puce></div>
        <div className="grand-chiffre" title={`${mad(vente ? k.ht : k.ttc)} MAD`}>{montant(vente ? k.ht : k.ttc)[0]}<span className="unite">{montant(vente ? k.ht : k.ttc)[1]}</span></div>
        <div className="resume-pied">
          <span><strong>{entier(k.nombre)}</strong> factures</span>
          <span title={`${mad(vente ? k.ttc : k.ht)} MAD`}><strong>{montant(vente ? k.ttc : k.ht).join(' ')}</strong> {vente ? 'TTC' : 'HT'}</span>
        </div>
      </section>
      <section className="carte resume-reste" aria-labelledby="resume-reste">
        <h2 id="resume-reste">{vente ? 'Reste à encaisser' : 'Reste à payer'}</h2>
        <div className="reste-ligne">
          <div className="montant-reste">{montant(k.reste)[0]}<span>{montant(k.reste)[1]}</span></div>
          <span className="anneau-reste" role="img" aria-label={`${centre} du montant TTC reste ${vente ? 'à encaisser' : 'à payer'}`}>
            <svg viewBox="0 0 80 80" aria-hidden="true">
              <circle cx="40" cy="40" r="32" className="piste-anneau" />
              <circle cx="40" cy="40" r="32" pathLength={100} className="valeur-anneau" strokeDasharray={`${Math.min(100, Math.max(0, part))} 100`} transform="rotate(-90 40 40)" />
            </svg>
            <span>{centre}</span>
          </span>
        </div>
        <span className="detail-reste">{mad(k.reste)} MAD sur {mad(k.ttc)} MAD TTC</span>
      </section>
    </div>
  )
}

/** Filtres des documents en une barre (maquettes) : champs avec leur nom au-dessus, case « Non réglés », bouton.
 *  La période est dans l'en-tête (Periode) : ses dates et la vue sont gardées en champs cachés. */
function FiltresDocuments({ cfg, p, du, au, commerciaux }: { cfg: (typeof DOMAINES)[0 | 1]; p: Params; du: string; au: string; commerciaux: [string, string][] | null }) {
  const champ = (label: string, name: string, placeholder: string, flex = '1 1 0') => (
    <label className="champ-pilule" style={{ flex }}>
      <span>{label}</span>
      <input name={name} defaultValue={lire(p, name)} placeholder={placeholder} />
    </label>
  )
  return (
    <div className="bloc-pilule">
      <FormulaireGet className="filtres-pilule" aria-label="Filtres de recherche">
        <input type="hidden" name="du" value={du} />
        <input type="hidden" name="au" value={au} />
        {champ('N° pièce', 'piece', cfg.exPiece)}
        {champ(cfg.code, 'tiers', cfg.exCode)}
        {champ(cfg.intitule, 'intitule', cfg.exIntitule, '2 1 0')}
        {commerciaux && (
          <label className="champ-pilule" style={{ flex: '1.3 1 0' }}>
            <span>Commercial</span>
            <select name="commercial" defaultValue={lire(p, 'commercial')}>
              {commerciaux.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        )}
        <label className="case-pilule"><input type="checkbox" name="non_regles" value="1" defaultChecked={lire(p, 'non_regles') === '1'} />Non réglés</label>
        <button type="submit" className="principal">Appliquer</button>
      </FormulaireGet>
      <p className="doux petit">Les filtres s&apos;appliquent à tous les types de documents ; « Non réglés » : reste à payer &gt; 0.</p>
    </div>
  )
}

/** Page Gestion des Ventes (domaine 0) ou des Achats (domaine 1). */
export default async function Documents({ domaine, p, chemin }: { domaine: 0 | 1; p: Params; chemin: string }) {
  const cfg = DOMAINES[domaine]
  const s = await session()
  const collab = estCollaborateur(s)
  const defaut = anneeEnCours()
  const analyse = lire(p, 'vue') === 'analyse'
  const du = lire(p, 'du') || defaut.debut, au = lire(p, 'au') || defaut.fin
  const entete = <Entete titre={cfg.titre} sousTitre={cfg.sous} actions={<Periode p={p} du={du} au={au} label={analyse ? "Période d'analyse" : 'Période'} />} />
  if (collab && domaine === 1) return <Page theme={domaine === 1 ? 'rouge' : 'emeraude'}>{entete}<Interdit /></Page>
  // Vue : documents (liste et détail) ou analyse
  const vues = (
    <Onglets items={[
      { nom: 'Documents', href: lien(chemin, p, { vue: undefined }), actif: !analyse },
      { nom: 'Analyse', href: lien(chemin, p, { vue: 'analyse', page: undefined, piece_doc: undefined }), actif: analyse },
    ]} />
  )
  if (analyse) {
    return (
      <Page theme={domaine === 1 ? 'rouge' : 'emeraude'}>
        {entete}{vues}
        {domaine === 0 ? <AnalyseVentes p={p} chemin={chemin} du={du} au={au} /> : <AnalyseAchats du={du} au={au} />}
      </Page>
    )
  }

  const filtres = {
    domaine, piece: lire(p, 'piece'), tiers: lire(p, 'tiers'), intitule: lire(p, 'intitule'),
    date_from: du, date_to: au,
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
    <Page theme={domaine === 1 ? 'rouge' : 'emeraude'}>
      {entete}
      {vues}
      <Resume domaine={domaine} k={r.kpis} du={filtres.date_from} au={filtres.date_to} />
      <FiltresDocuments cfg={cfg} p={p} du={du} au={au} commerciaux={collab ? null : optionsCommerciaux(collaborateurs)} />
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
