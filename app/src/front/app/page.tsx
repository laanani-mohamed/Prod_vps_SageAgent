import { Suspense } from 'react'
import Page from '../components/Page'
import { Carte, Entete, Interdit, Kpis, Onglets, Periode, Puce, Tableau } from '../components/ui'
import { api, estCollaborateur, session } from '../lib/api'
import { court, date, entier, mad, pct } from '../lib/format'
import { anneeEnCours, lien, lire, type Params } from '../lib/params'

/** Jauge demi-cercle : part de l'objectif atteinte (plafonnée à 100 % pour le dessin). */
function Jauge({ valeur }: { valeur: number | null }) {
  const p = Math.min(100, Math.max(0, valeur ?? 0))
  return (
    <svg viewBox="0 0 200 110" className="jauge" role="img" aria-label={`${pct(valeur)} de l'objectif`}>
      <path d="M15 100 A85 85 0 0 1 185 100" pathLength={100} className="fond-jauge" />
      <path d="M15 100 A85 85 0 0 1 185 100" pathLength={100} className="valeur-jauge" strokeDasharray={`${p} 100`} />
      <text x="100" y="92" textAnchor="middle">{pct(valeur)}</text>
    </svg>
  )
}

/** Anneau : un taux en % (0 à 100). */
function Anneau({ nom, taux, valeur, detail }: { nom: string; taux: number | null; valeur: string; detail: string }) {
  return (
    <div className="anneau">
      <svg viewBox="0 0 120 120" role="img" aria-label={`${nom} : ${valeur}`}>
        <circle cx="60" cy="60" r="50" pathLength={100} className="fond-jauge" />
        <circle cx="60" cy="60" r="50" pathLength={100} className="valeur-jauge" strokeDasharray={`${Math.min(100, Math.max(0, taux ?? 0))} 100`} transform="rotate(-90 60 60)" />
        <text x="60" y="66" textAnchor="middle">{valeur}</text>
      </svg>
      <div><strong>{nom}</strong><span className="doux petit">{detail}</span></div>
    </div>
  )
}

const CLASSEMENTS = { clients: 'Top Clients', fournisseurs: 'Top Fournisseurs', familles: 'Top Familles' } as const
const ATTENTE = <p className="vide">Calcul des indicateurs…</p>

/** Indicateurs analytiques (calcul long côté API, ~10 s) : affichés dès qu'ils arrivent. */
async function Anneaux({ analytique }: { analytique: Promise<any> }) {
  const a = await analytique
  return (
    <Carte span={3} titre="Indicateurs analytiques">
      <div className="anneaux">
        <Anneau nom="Marge brute" taux={a?.taux_marge ?? null} valeur={pct(a?.taux_marge)} detail={`${court(a?.marge_brute)} de marge`} />
        <Anneau nom="Factures impayées" taux={a?.taux_impayes ?? null} valeur={pct(a?.taux_impayes)}
          detail={`${entier(a?.nb_factures_impayees)} impayées sur ${entier(a?.nb_factures_total)} factures`} />
        <Anneau nom="Taux de retour" taux={a?.taux_retour ?? null} valeur={pct(a?.taux_retour)}
          detail={`${entier(a?.nb_bon_retour)} bons de retour sur ${entier(a?.nb_fac)} factures`} />
        <Anneau nom="Conversion devis → facture" taux={a?.taux_conversion ?? null} valeur={pct(a?.taux_conversion)}
          detail={`${entier(a?.nb_fac)} factures · ${entier(a?.nb_devis)} devis`} />
      </div>
    </Carte>
  )
}

async function Classements({ analytique, p, collab }: { analytique: Promise<any>; p: Params; collab: boolean }) {
  const a = await analytique
  const onglet = (lire(p, 'classement') || 'clients') as keyof typeof CLASSEMENTS
  const lignes = onglet === 'fournisseurs'
    ? (a?.top_fournisseurs ?? []).slice(0, 10).map((r: any) => ({ nom: r.ct_intitule, v: r.encours, pct: r.pct_encours }))
    : onglet === 'familles'
      ? (a?.top_familles ?? []).slice(0, 10).map((r: any) => ({ nom: r.fa_intitule, v: r.ca_ht, pct: r.pct_ca }))
      : (a?.top_clients ?? []).slice(0, 10).map((r: any) => ({ nom: r.ct_intitule, v: r.ca_ht, pct: r.pct_ca }))
  const maxPct = Math.max(...lignes.map((l: any) => l.pct ?? 0), 1)
  const onglets = (
    <Onglets items={Object.entries(CLASSEMENTS).map(([cle, nom]) => ({
      nom, href: lien('/', p, { classement: cle }), actif: onglet === cle, interdit: collab && cle === 'fournisseurs',
    }))} />
  )
  return (
    <Carte titre="Classements" note={onglets}>
      {collab && onglet === 'fournisseurs' ? <Interdit /> : (
        <Tableau
          colonnes={[{ nom: '#', largeur: '40px' }, { nom: onglet === 'clients' ? 'Nom client' : onglet === 'familles' ? 'Famille' : 'Nom fournisseur' },
            { nom: onglet === 'fournisseurs' ? 'Encours' : 'CA HT', droite: true, largeur: '180px' },
            { nom: onglet === 'fournisseurs' ? '% encours global' : '% CA global', droite: true, largeur: '200px' }]}
          lignes={lignes.map((l: any, i: number) => ({
            cellules: [i + 1, l.nom, mad(l.v), (
              <span className="part" key="p"><span className="piste"><span style={{ width: `${((l.pct ?? 0) / maxPct) * 100}%` }} /></span>{pct(l.pct)}</span>
            )],
          }))}
        />
      )}
    </Carte>
  )
}

export default async function TableauDeBord({ searchParams }: { searchParams: Promise<Params> }) {
  const p = await searchParams
  const s = await session()
  const collab = estCollaborateur(s)
  const defaut = anneeEnCours()
  const du = lire(p, 'du') || defaut.debut
  const au = lire(p, 'au') || defaut.fin
  // Une seule requête analytique, attendue par les deux blocs qui en dépendent
  const analytique = api(`/api/bi/dashboard/analytique?${new URLSearchParams({ client_schema: s.client ?? '', date_from: du, date_to: au })}`)
  const d = await api('/api/bi/dashboard', { client_schema: s.client, date_from: du, date_to: au })
  const k = d?.kpis ?? {}

  return (
    <Page theme="indigo">
      <Entete titre="Tableau de Bord — Indicateurs de Performance" sousTitre={`Période : du ${date(du)} au ${date(au)}`}
        actions={<Periode p={p} du={du} au={au} />} />

      <div className="grille-5">
        <Carte span={2} titre="Chiffre d'Affaires (objectif 25 MMAD)" note={<Puce>{du.slice(0, 4) === au.slice(0, 4) ? `YTD ${au.slice(0, 4)}` : 'Période'}</Puce>}>
          <div className="grand-chiffre">{court(k.chiffre_affaires)}</div>
          <Jauge valeur={k.pct_objectif_ca ?? null} />
          <div className="pied-carte">
            <span>Chiffre d&apos;Affaires N-1</span>
            <strong>{court(k.ca_n_minus_1)}
              {k.ca_evolution_pct != null && <span className={k.ca_evolution_pct < 0 ? 'mauvais' : 'bon'}> · {pct(k.ca_evolution_pct, true)}</span>}
            </strong>
          </div>
        </Carte>
        <Suspense fallback={<Carte span={3} titre="Indicateurs analytiques">{ATTENTE}</Carte>}>
          <Anneaux analytique={analytique} />
        </Suspense>
      </div>

      <Kpis items={[
        { nom: 'Encours clients', v: court(k.encours_clients), sous: `${pct(k.pct_limite_encours)} de la limite 30 MMAD` },
        { nom: 'Clients actifs', v: entier(k.nb_clients_actifs), sous: 'au moins une facture de vente' },
        { nom: 'Total achats', v: court(k.total_achats) },
        { nom: 'Valeur du stock', v: court(k.valeur_stock) },
        { nom: 'Dettes fournisseurs', v: court(k.dettes_fournisseurs),
          sous: k.pct_limite_dettes == null ? undefined : `${pct(k.pct_limite_dettes)} de la limite 20 MMAD`,
          ton: (k.pct_limite_dettes ?? 0) > 100 ? 'mauvais' : undefined },
      ]} />

      <Suspense fallback={<Carte titre="Classements">{ATTENTE}</Carte>}>
        <Classements analytique={analytique} p={p} collab={collab} />
      </Suspense>
    </Page>
  )
}
