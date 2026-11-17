import { notFound } from 'next/navigation'
import Page from '../../../components/Page'
import { Barres, Carte, Champ, Entete, Filtres, Interdit, Kpis, Onglets, Pagination, Periode, SousBloc, Tableau, type Kpi } from '../../../components/ui'
import { api, estCollaborateur, session, vue } from '../../../lib/api'
import { entier, mad, pct } from '../../../lib/format'
import { anneeEnCours, lien, lire, type Params } from '../../../lib/params'

const ONGLETS = { articles: 'Articles', clients: 'Clients', fournisseurs: 'Fournisseurs', depots: 'Dépôts', familles: 'Familles' }
const DIRECTEUR = ['fournisseurs', 'depots']   // sections sans commercial : 🚫 pour un collaborateur
const ton = (v?: number | null) => (v == null ? undefined : v < 0 ? 'mauvais' : 'bon') as Kpi['ton']

/** Ligne « Cliquez sur… | n sur total » au-dessus d'une liste. */
const Legende = ({ aide, n, total, quoi }: { aide: string; n: number; total: number; quoi: string }) => (
  <div className="carte-titre doux petit"><span>{aide}</span><span>{entier(n)} sur {entier(total)} {quoi}</span></div>
)

export default async function FichierDeBase({ params, searchParams }: { params: Promise<{ onglet: string }>; searchParams: Promise<Params> }) {
  const { onglet } = await params
  if (!(onglet in ONGLETS)) notFound()
  const p = await searchParams
  const s = await session()
  const collab = estCollaborateur(s)
  const chemin = `/fichier-de-base/${onglet}`
  const defaut = anneeEnCours()
  const du = lire(p, 'du') || defaut.debut, au = lire(p, 'au') || defaut.fin
  const page = lire(p, 'page') || 1
  const periode = <Periode p={p} du={du} au={au} label="Période d'analyse" />

  const n = await vue('compteurs')
  const haut = <>
    <Entete titre="Fichier de Base" sousTitre="Référentiel Sage : articles, tiers, dépôts et familles" />
    <Onglets items={Object.entries(ONGLETS).map(([c, nom]) => ({
      nom, nombre: n[c], href: `/fichier-de-base/${c}`, actif: c === onglet, interdit: collab && DIRECTEUR.includes(c),
    }))} />
  </>
  if (collab && DIRECTEUR.includes(onglet)) return <Page theme="ocean">{haut}<Interdit /></Page>

  let contenu: React.ReactNode
  if (onglet === 'articles') {
    const [r, familles] = await Promise.all([
      vue('articles', { design: lire(p, 'design'), ref: lire(p, 'ref'), famille: lire(p, 'famille'), page, taille: 10 }),
      api('/api/referentiel/familles', { client_schema: s.client }),
    ])
    const ref = lire(p, 'art') || r.lignes[0]?.ar_ref
    const a = ref && (await vue('article', { ref, date_from: du, date_to: au }))
    contenu = <>
      <Carte>
        <Filtres cadre={false} colonnes="repeat(3, minmax(0, 1fr)) auto">
          <Champ label="Recherche par désignation" name="design" defaut={lire(p, 'design')} />
          <Champ label="Recherche par référence" name="ref" defaut={lire(p, 'ref')} />
          <Champ label="Famille" name="famille" defaut={lire(p, 'famille')}
            options={[['', 'Toutes les familles'], ...(familles?.data ?? []).map((f: any): [string, string] => [f.fa_codefamille, `${f.fa_codefamille} · ${f.fa_intitule ?? ''}`])]} />
        </Filtres>
        <Legende aide="Cliquez sur un article pour voir ses statistiques" n={r.lignes.length} total={r.total} quoi="articles" />
        <Tableau
          colonnes={[{ nom: 'Réf.', largeur: '140px' }, { nom: 'Désignation' }, { nom: 'Famille', largeur: '110px' },
            { nom: 'Prix achat', droite: true, largeur: '110px' }, { nom: 'Prix vente', droite: true, largeur: '110px' }, { nom: 'Stock actuel', droite: true, largeur: '110px' }]}
          lignes={r.lignes.map((l: any) => ({
            cle: l.ar_ref, actif: l.ar_ref === ref, href: lien(chemin, p, { art: l.ar_ref }),
            cellules: [l.ar_ref, l.ar_design, l.fa_codefamille, mad(l.ar_prixach), mad(l.ar_prixven), entier(l.qte_stock_totale)],
          }))}
          vide="Aucun article pour ces filtres."
        />
        <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(x) => lien(chemin, p, { page: x })} />
      </Carte>
      {a && (
        <Carte>
          <div className="entete-detail">
            <div>
              <h2>{a.article.ref} · Famille {a.article.famille} ({a.article.famille_nom ?? '—'})</h2>
              <p className="doux">{a.article.design}</p>
            </div>
            {periode}
          </div>
          {a.article.prix_achat === 0 && (
            <p className="carte refus">Prix d&apos;achat non renseigné dans Sage (0,00) : le coût d&apos;achat, la marge et la rentabilité ne sont pas fiables pour cet article.</p>
          )}
          <Kpis items={[
            { nom: 'Stock actuel', v: entier(a.article.stock), sous: 'tous dépôts' },
            { nom: 'Quantité vendue', v: entier(a.kpis.quantite_vendue), sous: 'factures de vente' },
            { nom: 'CA HT', v: `${mad(a.kpis.ca_ht)} DH` },
            { nom: "Coût d'achat total", v: mad(a.kpis.cout_achat), sous: "quantité × prix d'achat" },
          ]} />
          <Kpis items={[
            { nom: 'Marge brute', v: `${mad(a.kpis.marge_brute)} DH` },
            { nom: 'Taux de marge', v: pct(a.kpis.taux_marge_pct) },
            { nom: 'Rentabilité globale', v: pct(a.kpis.rentabilite_pct), sous: a.kpis.rentabilite_pct == null ? "coût d'achat nul" : 'marge ÷ coût' },
          ]} />
          <div className="grille">
            <SousBloc titre="Top 5 clients (ventes)">
              <Tableau colonnes={[{ nom: 'Client' }, { nom: 'Qté', droite: true, largeur: '80px' }, { nom: 'CA HT', droite: true, largeur: '120px' }]}
                lignes={a.top_clients.map((c: any) => ({ cle: c.client, cellules: [c.client, entier(c.qte), mad(c.ca)] }))} vide="Aucune vente sur la période." />
            </SousBloc>
            <SousBloc titre="Détail du stock (dépôts)">
              {a.depots === null ? <Interdit /> : (
                <Tableau colonnes={[{ nom: 'Dépôt' }, { nom: 'Quantité', droite: true, largeur: '110px' }]}
                  lignes={a.depots.map((d: any) => ({ cle: d.depot, cellules: [d.depot, entier(d.qte)] }))} />
              )}
            </SousBloc>
          </div>
        </Carte>
      )}
    </>
  } else if (onglet === 'clients' || onglet === 'fournisseurs') {
    const ctType = onglet === 'clients' ? 0 : 1
    const r = await vue('tiers', { ct_type: ctType, nom: lire(p, 'nom'), ref: lire(p, 'ref'), page, taille: 10 })
    const num = lire(p, 'tiers') || r.lignes[0]?.ct_num
    // Compte choisi : dans la page affichée, sinon recherché par son code (lien direct, autre page)
    const choisi = r.lignes.find((l: any) => l.ct_num === num)
      ?? (num ? (await vue('tiers', { ct_type: ctType, ref: num, taille: 200 })).lignes.find((l: any) => l.ct_num === num) : undefined)
    const st = num && (await api('/api/bi/stats-tiers', { client_schema: s.client, ct_num: num, ct_type: ctType, date_from: du, date_to: au }))?.data?.[0]
    const k = st?.kpis ?? {}
    const qui = ctType ? 'fournisseur' : 'client'
    contenu = <>
      <Carte>
        <Filtres cadre={false} colonnes="repeat(2, minmax(0, 1fr)) auto">
          <Champ label="Recherche par nom" name="nom" defaut={lire(p, 'nom')} />
          <Champ label="Recherche par référence" name="ref" defaut={lire(p, 'ref')} />
        </Filtres>
        <Legende aide={`Cliquez sur un ${qui} pour voir ses statistiques`} n={r.lignes.length} total={r.total} quoi={`comptes ${qui}s`} />
        <Tableau
          colonnes={[{ nom: ctType ? 'Code fournisseur' : 'Code client', largeur: '140px' }, { nom: 'Raison sociale' }, { nom: 'ICE', largeur: '170px' }, { nom: 'Ville', largeur: '150px' }]}
          lignes={r.lignes.map((l: any) => ({
            cle: l.ct_num, actif: l.ct_num === num, href: lien(chemin, p, { tiers: l.ct_num }),
            cellules: [l.ct_num, l.ct_intitule, l.ice || '—', l.ct_ville ?? '—'],
          }))}
          vide="Aucun compte pour ces filtres."
        />
        <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(x) => lien(chemin, p, { page: x })} />
      </Carte>
      {st && (
        <Carte>
          <div className="entete-detail">
            <div>
              <div className="sous-titre">Statistiques du {qui}</div>
              <h2>{num} · {choisi?.ct_intitule ?? ''}</h2>
            </div>
            {periode}
          </div>
          {ctType === 0 ? <>
            <Kpis items={[
              { nom: 'CA HT', v: mad(k.montant_ht), sous: k.evolution_pct == null ? undefined : <span className={ton(k.evolution_pct)}>{pct(k.evolution_pct, true)} vs N-1</span> },
              { nom: 'Factures / avoirs', v: `${entier(k.nb_factures)} / ${entier(k.nb_avoirs)}` },
              { nom: 'Encours', v: mad(k.encours), sous: 'TTC restant dû' },
              { nom: 'Marge brute', v: mad(k.marge_brute), sous: `${pct(k.taux_marge_pct)} du CA` },
              { nom: 'Transformation des devis', v: pct(k.taux_transformation_devis_pct), sous: `${entier(k.nb_devis)} devis` },
            ]} />
            <div className="grille">
              <SousBloc titre="Top articles achetés">
                <Tableau colonnes={[{ nom: 'Article' }, { nom: 'Qté', droite: true, largeur: '70px' }, { nom: 'Montant HT', droite: true, largeur: '120px' }]}
                  lignes={(st.top_articles ?? []).map((x: any) => ({ cle: x.ar_ref, cellules: [`${x.ar_ref} · ${x.designation}`, entier(x.qte), mad(x.montant_ht)] }))} />
              </SousBloc>
              <div className="pile-blocs">
                <SousBloc titre="Familles achetées"><Barres items={(st.familles ?? []).slice(0, 6).map((x: any) => ({ nom: x.famille, v: x.pct, libelle: pct(x.pct) }))} /></SousBloc>
                <SousBloc titre="Commerciaux" note="commercial porté par la facture">
                  <Barres items={(st.commerciaux ?? []).map((x: any) => ({ nom: x.commercial, v: x.pct, libelle: `${pct(x.pct)} du CA` }))} />
                </SousBloc>
              </div>
            </div>
          </> : <>
            <div className="sous-titre">Indicateurs de base</div>
            <Kpis items={[
              { nom: 'Achats HT', v: mad(k.montant_ht), sous: k.evolution_pct == null ? undefined : <span className={ton(k.evolution_pct)}>{pct(k.evolution_pct, true)} vs N-1 ({mad(k.montant_ht_n1)})</span> },
              { nom: 'Factures / avoirs', v: `${entier(k.nb_factures)} / ${entier(k.nb_avoirs)}` },
              { nom: 'Dettes', v: mad(k.dettes), sous: "tout l'historique" },
            ]} />
            <div className="sous-titre">Indicateurs d&apos;analyse</div>
            <Kpis items={[
              { nom: 'Part des achats', v: pct(k.part_achats_pct), sous: k.rang ? `rang ${k.rang} sur ${k.nb_fournisseurs_actifs} actifs` : undefined },
              { nom: 'Délai de livraison', v: k.delai_moyen_jours == null ? 'N/A' : `${entier(k.delai_moyen_jours)} jours`, sous: 'moyenne BC → BL' },
              { nom: 'Évolution des prix', v: pct(k.evolution_prix_ponderee_pct, true), sous: `${entier(k.nb_articles_prix_compares)} articles comparés` },
            ]} />
            <SousBloc titre="Top articles achetés">
              <Tableau
                colonnes={[{ nom: 'Réf.', largeur: '110px' }, { nom: 'Désignation' }, { nom: 'Qté', droite: true, largeur: '70px' }, { nom: 'Achats HT', droite: true, largeur: '110px' },
                  { nom: 'Prix moyen', droite: true, largeur: '100px' }, { nom: '1er prix', droite: true, largeur: '90px' }, { nom: 'Dernier prix', droite: true, largeur: '100px' }, { nom: 'Évol. prix', droite: true, largeur: '90px' }]}
                lignes={(st.top_articles ?? []).map((x: any) => ({
                  cle: x.ar_ref, cellules: [x.ar_ref, x.designation, entier(x.qte), mad(x.montant_ht), mad(x.prix_moyen), mad(x.premier_prix), mad(x.dernier_prix),
                    <span key="e" className={(x.evolution_prix_pct ?? 0) > 0 ? 'mauvais' : undefined}>{pct(x.evolution_prix_pct, true)}</span>],
                }))} />
            </SousBloc>
          </>}
        </Carte>
      )}
    </>
  } else if (onglet === 'depots') {
    const r = await vue('depots')
    contenu = (
      <Carte titre="Dépôts de stock" note={`${entier(r.depots.length)} dépôts · nombre d'articles distincts référencés par dépôt`}>
        <div className="cartes-depots">
          {r.depots.map((d: any) => (
            <div key={d.de_no} className="carte-depot">
              <span className="numero-depot">{d.de_no}</span>
              <strong>{d.de_intitule ?? `Dépôt ${d.de_no}`}</strong>
              <span className="doux">Nombre d&apos;articles <strong>{entier(d.articles)}</strong></span>
            </div>
          ))}
        </div>
      </Carte>
    )
  } else {
    const choix = lire(p, 'choix').split(',').filter(Boolean)
    const r = await vue('familles', { nom: lire(p, 'nom'), code: lire(p, 'code'), choix: choix.join(','), page, page_articles: lire(p, 'page_articles') || 1, taille: 10 })
    const basculer = (code: string) => (choix.includes(code) ? choix.filter((c) => c !== code) : [...choix, code]).join(',')
    contenu = <>
      <Carte>
        <Filtres cadre={false} colonnes="repeat(2, minmax(0, 1fr)) auto">
          <input type="hidden" name="choix" value={choix.join(',')} />
          <Champ label="Recherche par intitulé" name="nom" defaut={lire(p, 'nom')} />
          <Champ label="Recherche par code" name="code" defaut={lire(p, 'code')} />
        </Filtres>
        <Legende aide="Sélectionnez une ou plusieurs familles pour afficher leurs articles" n={r.lignes.length} total={r.total} quoi="familles" />
        <Tableau
          colonnes={[{ nom: 'Code famille', largeur: '130px' }, { nom: 'Intitulé' }, { nom: 'Suivi stock', largeur: '110px' }, { nom: "Nombre d'articles", droite: true, largeur: '140px' }, { nom: 'Unité de vente', largeur: '130px' }]}
          lignes={r.lignes.map((f: any) => ({
            cle: f.fa_codefamille, actif: choix.includes(f.fa_codefamille), href: lien(chemin, p, { choix: basculer(f.fa_codefamille), page_articles: undefined }),
            cellules: [f.fa_codefamille, f.fa_intitule, f.suivi ?? '—', entier(f.nb_articles), f.u_intitule ?? '—'],
          }))}
        />
        <Pagination total={r.total} page={r.page} taille={r.taille_page} href={(x) => lien(chemin, p, { page: x })} />
      </Carte>
      {r.articles && (
        <Carte titre={`Articles des familles sélectionnées : ${choix.join(', ')}`} note={`${entier(r.articles.total)} articles · triés par stock`}>
          <Tableau
            colonnes={[{ nom: 'Réf.', largeur: '140px' }, { nom: 'Nom article' }, { nom: 'Famille', largeur: '110px' }, { nom: 'Prix achat', droite: true, largeur: '110px' },
              { nom: 'Prix vente', droite: true, largeur: '110px' }, { nom: 'Stock actuel', droite: true, largeur: '110px' }]}
            lignes={r.articles.lignes.map((a: any) => ({ cle: a.ar_ref, cellules: [a.ar_ref, a.ar_design, a.fa_codefamille, mad(a.ar_prixach), mad(a.ar_prixven), entier(a.qte_stock_totale)] }))}
          />
          <Pagination total={r.articles.total} page={r.articles.page} taille={r.articles.taille_page} href={(x) => lien(chemin, p, { page_articles: x })} />
        </Carte>
      )}
    </>
  }

  return <Page theme="ocean">{haut}{contenu}</Page>
}
