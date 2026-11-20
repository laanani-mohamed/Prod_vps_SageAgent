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

const OBJECTIF_CA = 10_000_000   // objectif annuel (même valeur que OBJECTIF_CA de api/bi/use_cases/objectifs_uc.py)
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const brefMAD = (v: number) => (v >= 1e6 ? court(v).replace(' MMAD', ' M') : `${entier(Math.round(v / 1e3))} K`)

/** Progression du CA HT : CA de chaque mois de la période (montant au-dessus, exact au survol). */
async function ProgressionCA({ ventes, objectif }: { ventes: Promise<any>; objectif: number | null }) {
  const mois: { mois: string; ca_ht: number }[] = (await ventes)?.data ?? []
  const W = 560, H = 300, G = 8, HAUT = 24, BAS = 34, zone = H - HAUT - BAS
  if (!mois.length) return <Carte titre="Progression du CA HT"><p className="vide">Aucune facture sur la période.</p></Carte>
  const total = mois.reduce((s, m) => s + m.ca_ht, 0)
  const max = Math.max(...mois.map((m) => m.ca_ht), 1)
  const pas = (W - 2 * G) / mois.length, larg = Math.min(pas * 0.62, 46)
  const xc = (i: number) => G + pas * (i + 0.5)
  const resume = `CA HT ${court(total)} sur ${mois.length} mois${objectif ? `, soit ${pct(total / objectif * 100)} de l'objectif ${court(objectif)}` : ''}`
  return (
    <Carte titre="Progression du CA HT" note={<span className="legende"><span><i className="b" />CA HT du mois</span></span>}>
      <svg className="progression" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={resume}>
        <line x1={G} x2={W - G} y1={HAUT + zone} y2={HAUT + zone} stroke="var(--bord)" />
        {mois.map((m, i) => {
          const h = Math.max(1, (m.ca_ht / max) * zone * 0.9)
          const n = Number(m.mois.slice(5, 7)) - 1
          return (
            <g key={m.mois}>
              <rect x={xc(i) - larg / 2} y={HAUT + zone - h} width={larg} height={h} rx="4" fill="var(--accent)" opacity="0.85"><title>{`${MOIS[n]} ${m.mois.slice(0, 4)} : ${mad(m.ca_ht)} MAD HT`}</title></rect>
              <text x={xc(i)} y={HAUT + zone - h - 5} textAnchor="middle" className="etiquette">{brefMAD(m.ca_ht)}</text>
              <text x={xc(i)} y={H - 12} textAnchor="middle" className="etiquette">{MOIS[n]}</text>
            </g>
          )
        })}
      </svg>
      <p className="doux petit">{resume}.</p>
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
            { nom: onglet === 'fournisseurs' ? 'Encours' : 'CA HT', droite: true, largeur: '108px' },
            { nom: onglet === 'fournisseurs' ? '% encours' : '% CA', droite: true, largeur: '92px' }]}
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
  const ventes = api('/api/bi/rapport/ca', { client_schema: s.client, date_from: du, date_to: au, group_by: 'mois' })
  const d = await api('/api/bi/dashboard', { client_schema: s.client, date_from: du, date_to: au })
  const k = d?.kpis ?? {}

  return (
    <Page theme="indigo">
      <Entete titre="Tableau de Bord" sousTitre={`Période : du ${date(du)} au ${date(au)}`}
        actions={<Periode p={p} du={du} au={au} />} />

      <div className="grille-5">
        <Carte span={2} titre="Chiffre d'Affaires (objectif 10 MMAD)" note={<Puce>{du.slice(0, 4) === au.slice(0, 4) ? `YTD ${au.slice(0, 4)}` : 'Période'}</Puce>}>
          <div className="grand-chiffre">{court(k.chiffre_affaires)}</div>
          <Jauge valeur={k.pct_objectif_ca ?? null} />
          <div className="pied-carte">
            <span>Chiffre d&apos;Affaires {Number(du.slice(0, 4)) - 1}</span>
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
        { nom: 'Encours clients', v: court(k.encours_clients), progres: k.pct_limite_encours, sous: `${pct(k.pct_limite_encours)} de la limite 30 MMAD` },
        { nom: 'Clients actifs', v: entier(k.nb_clients_actifs), sous: 'au moins une facture de vente' },
        { nom: 'Total achats', v: court(k.total_achats) },
        { nom: 'Valeur du stock', v: court(k.valeur_stock) },
        { nom: 'Dettes fournisseurs', v: court(k.dettes_fournisseurs),
          progres: k.pct_limite_dettes, sous: k.pct_limite_dettes == null ? undefined : `${pct(k.pct_limite_dettes)} de la limite 20 MMAD` },
      ]} />

      <div className="grille">
        <Suspense fallback={<Carte titre="Progression du CA HT">{ATTENTE}</Carte>}>
          <ProgressionCA ventes={ventes} objectif={du.slice(0, 4) === au.slice(0, 4) ? OBJECTIF_CA : null} />
        </Suspense>
        <Suspense fallback={<Carte titre="Classements">{ATTENTE}</Carte>}>
          <Classements analytique={analytique} p={p} collab={collab} />
        </Suspense>
      </div>
    </Page>
  )
}
