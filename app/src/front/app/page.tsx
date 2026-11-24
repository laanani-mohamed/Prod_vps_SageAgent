import Link from 'next/link'
import { Suspense } from 'react'
import Page from '../components/Page'
import { Carte, Entete, Interdit, Kpis, Onglets, Periode, Puce, Tableau } from '../components/ui'
import { api, estCollaborateur, session, vue } from '../lib/api'
import { annees, court, date, decaler, entier, mad, montant, pct } from '../lib/format'
import { anneeEnCours, lien, lire, type Params } from '../lib/params'

/** Jauge demi-cercle : part de l'objectif atteinte (plafonnée à 100 % pour le dessin). */
function Jauge({ valeur }: { valeur: number | null }) {
  const p = Math.min(100, Math.max(0, valeur ?? 0))
  return (
    <svg viewBox="0 0 200 110" className="jauge" role="img" aria-label={`${pct(valeur)} de l'objectif`}>
      <path d="M15 100 A85 85 0 0 1 185 100" pathLength={100} className="fond-jauge" />
      {p > 0 && <path d="M15 100 A85 85 0 0 1 185 100" pathLength={100} className="valeur-jauge" strokeDasharray={`${p} 100`} />}
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

const CLASSEMENTS = { clients: 'Top Clients', fournisseurs: 'Top Fournisseurs', familles: 'Top Familles', commerciaux: 'Top Commerciaux' } as const
const ATTENTE = <p className="vide">Calcul des indicateurs…</p>

/** Indicateurs analytiques (calcul long côté API, ~10 s) : affichés dès qu'ils arrivent. */
async function Anneaux({ analytique }: { analytique: Promise<any> }) {
  const a = await analytique
  return (
    <Carte titre="Indicateurs analytiques">
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
async function ProgressionCA({ ventes, objectif, p, du, au, client }: {
  ventes: Promise<any>; objectif: number | null; p: Params; du: string; au: string; client: string | null
}) {
  // Onglets : année de la période et les deux années précédentes, sur les mêmes mois (période décalée d'un ou deux ans,
  // comme les lignes « Chiffre d'Affaires » de la carte CA)
  const an = Number(au.slice(0, 4))
  const choisi = Number(lire(p, 'ca')) || an
  const annees = [an, an - 1, an - 2]
  const courant = choisi === an || !annees.includes(choisi)
  const onglets = (
    <Onglets items={annees.map((a) => ({ nom: String(a), href: lien('/', p, { ca: a === an ? undefined : a }), actif: courant ? a === an : a === choisi }))} />
  )
  const ecart = an - choisi
  const [deb, fin] = courant ? [du, au] : [decaler(du, ecart), decaler(au, ecart)]
  const reponse = courant ? await ventes
    : await api('/api/bi/rapport/ca', { client_schema: client, date_from: deb, date_to: fin, group_by: 'mois' })
  const mois: { mois: string; ca_ht: number }[] = reponse?.data ?? []
  const W = 560, H = 300, G = 8, HAUT = 24, BAS = 34, zone = H - HAUT - BAS
  if (!mois.length) return <Carte titre="Progression du CA HT" note={onglets}><p className="vide">Aucune facture du {date(deb)} au {date(fin)}.</p></Carte>
  const total = mois.reduce((s, m) => s + m.ca_ht, 0)
  const max = Math.max(...mois.map((m) => m.ca_ht), 1)
  const pas = (W - 2 * G) / mois.length, larg = Math.min(pas * 0.62, 46)
  const xc = (i: number) => G + pas * (i + 0.5)
  const resume = courant
    ? `CA HT ${court(total)} sur ${mois.length} mois (du ${date(du)} au ${date(au)})${objectif ? `, soit ${pct(total / objectif * 100)} de l'objectif ${court(objectif)}` : ''}`
    : `CA HT ${court(total)} sur ${mois.length} mois (du ${date(deb)} au ${date(fin)}), mêmes mois qu'en ${an}`
  return (
    <Carte titre="Progression du CA HT" note={onglets}>
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

async function Classements({ analytique, plus, p, collab }: { analytique: Promise<any>; plus: Promise<any>; p: Params; collab: boolean }) {
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
      {collab && onglet === 'fournisseurs' ? <Interdit /> : onglet === 'commerciaux' ? <TopCommerciaux plus={plus} /> : (
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

/** Top Commerciaux : CA HT et marge des lignes de factures, clients facturés (commercial porté par la facture). */
async function TopCommerciaux({ plus }: { plus: Promise<any> }) {
  const lignes: any[] = (await plus)?.commerciaux ?? []
  const max = Math.max(...lignes.map((l) => l.part_ca ?? 0), 1)
  return (
    <>
      <Tableau
        colonnes={[{ nom: '#', largeur: '40px' }, { nom: 'Commercial' }, { nom: 'CA HT', droite: true, largeur: '120px' },
          { nom: 'Marge', droite: true, largeur: '120px' }, { nom: 'Clients', droite: true, largeur: '70px' }]}
        lignes={lignes.map((l, i) => ({
          cellules: [i + 1, l.nom, (
            <span className="part" key="ca">{mad(l.ca_ht)}<span className="piste"><span style={{ width: `${((l.part_ca ?? 0) / max) * 100}%` }} /></span></span>
          ), (
            <span key="m" className="cellule-double"><span className={l.marge < 0 ? 'mauvais' : undefined}>{mad(l.marge)}</span><span className="doux petit">{pct(l.taux_marge)}</span></span>
          ), entier(l.clients)],
        }))}
        vide="Aucune facture sur la période."
      />
      <p className="doux petit">Commercial porté par la facture ; « Non identifié » = factures sans commercial. Marge : même calcul que la marge brute.</p>
    </>
  )
}

const ICONES_ALERTE = {
  impayes: 'M12 8v4l3 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
  ruptures: 'M21 8l-9-5-9 5 9 5zM3 8v8l9 5 9-5V8M12 13v8',
  inactifs: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM17 8l5 5M22 8l-5 5',
}

/** Bandeau d'alertes : chaque carte renvoie vers la page où l'on traite le problème. */
async function Alertes({ plus, ruptures }: { plus: Promise<any>; ruptures: Promise<any> | null }) {
  const [t, r] = await Promise.all([plus, ruptures])
  const items = [
    t && { cle: 'impayes', ton: 'rouge', nb: t.alertes.impayes_90.clients, titre: 'clients à +90 jours',
      detail: `${court(t.alertes.impayes_90.montant_ttc)} TTC d'impayés de plus de 90 jours`, cible: 'Balance âgée', href: '/rapports/9' },
    r && { cle: 'ruptures', ton: 'orange', nb: r.ruptures, titre: 'ruptures en classe A',
      detail: `sur ${entier(r.articles_classe_a)} articles qui font 80 % du CA · ${court(r.ca_ht_12_mois)} de CA sur 12 mois`, cible: 'Stock', href: '/stock/alertes?type=rupture' },
    t && { cle: 'inactifs', ton: 'indigo', nb: t.alertes.clients_inactifs.clients, titre: "clients qui n'achètent plus",
      detail: `aucune facture depuis 90 jours · ${court(t.alertes.clients_inactifs.ca_ht_12_mois)} de CA avant`, cible: 'Avant visite', href: '/rapports/5' },
  ].filter(Boolean) as any[]
  if (!items.length) return null
  return (
    <nav className="alertes-tdb" aria-label="Alertes" style={{ '--n': items.length } as React.CSSProperties}>
      {items.map((a) => (
        <Link prefetch={false} key={a.cle} href={a.href} className={`alerte-tdb ${a.ton}`}>
          <span className="icone-alerte" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={ICONES_ALERTE[a.cle as keyof typeof ICONES_ALERTE]} /></svg>
          </span>
          <span className="texte-alerte">
            <span className="titre-alerte"><strong>{entier(a.nb)}</strong> {a.titre}</span>
            <span className="doux petit coupe" title={a.detail}>{a.detail}</span>
          </span>
          <span className="cible-alerte">{a.cible} ›</span>
        </Link>
      ))}
    </nav>
  )
}

/** Rythme : CA HT par jour écoulé ; requis : reste de l'objectif annuel ÷ jours restants (vert si le rythme suffit). */
function Rythme({ rythme }: { rythme: any }) {
  if (!rythme || rythme.actuel == null) return null
  const ok = rythme.requis == null || rythme.actuel >= rythme.requis
  const jour = (v: number | null) => (v == null ? 'N/A' : `${entier(Math.round(v))} MAD/j`)
  return (
    <div className="rythmes">
      <div className={`rythme ${ok ? 'bon' : 'mauvais'}`} title={`CA HT ÷ ${entier(rythme.jours_ecoules)} jours écoulés`}>
        <span>Rythme actuel</span><strong>{jour(rythme.actuel)}</strong>
      </div>
      {rythme.requis != null && (
        <div className="rythme" title={`Reste de l'objectif ÷ ${entier(rythme.jours_restants)} jours restants`}>
          <span>Requis par jour</span><strong>{jour(rythme.requis)}</strong>
        </div>
      )}
    </div>
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
  // Compléments (panier moyen, rythme, alertes, top commerciaux) ; ruptures de classe A : directeur seulement (stock)
  const plus = vue('tdb_plus', { date_from: du, date_to: au }).catch(() => null)
  const ruptures = collab ? null : vue('ruptures_a', { date_from: du, date_to: au }).catch(() => null)
  const [d, t] = await Promise.all([api('/api/bi/dashboard', { client_schema: s.client, date_from: du, date_to: au }), plus])
  const k = d?.kpis ?? {}
  const pm = t?.panier

  return (
    <Page theme="indigo">
      <Entete titre="Tableau de Bord" sousTitre={`Période : du ${date(du)} au ${date(au)}`}
        actions={<Periode p={p} du={du} au={au} />} />

      <Suspense fallback={null}>
        <Alertes plus={plus} ruptures={ruptures} />
      </Suspense>

      <div className="grille">
        <Carte titre="Chiffre d'Affaires (objectif 10 MMAD)" note={<Puce>{du.slice(0, 4) === au.slice(0, 4) ? `YTD ${au.slice(0, 4)}` : 'Période'}</Puce>}>
          <div className="ca-ligne">
            <div className="ca-gauche">
              <div className="grand-chiffre" title={`${mad(k.chiffre_affaires)} MAD HT`}>
                {montant(k.chiffre_affaires)[0]}<span className="unite">{montant(k.chiffre_affaires)[1]}</span>
              </div>
              <Jauge valeur={k.pct_objectif_ca ?? null} />
            </div>
            <Rythme rythme={t?.rythme} />
          </div>
          <div className="pied-carte">
            <span>Chiffre d&apos;Affaires {annees(t?.historique?.[0]?.du ?? `${Number(du.slice(0, 4)) - 1}`, t?.historique?.[0]?.au ?? `${Number(au.slice(0, 4)) - 1}`)}</span>
            <strong>{court(k.ca_n_minus_1)}
              {k.ca_evolution_pct != null && <span className={k.ca_evolution_pct < 0 ? 'mauvais' : 'bon'}> · {pct(k.ca_evolution_pct, true)}</span>}
            </strong>
          </div>
          {t?.historique?.[1] && (
            <div className="pied-carte">
              <span>Chiffre d&apos;Affaires {annees(t.historique[1].du, t.historique[1].au)}</span>
              <strong>{t.historique[1].ca_ht ? court(t.historique[1].ca_ht) : 'N/A'}
                {t.historique[1].evolution_pct != null && <span className={t.historique[1].evolution_pct < 0 ? 'mauvais' : 'bon'}> · {pct(t.historique[1].evolution_pct, true)}</span>}
              </strong>
            </div>
          )}
        </Carte>
        <Suspense fallback={<Carte titre="Indicateurs analytiques">{ATTENTE}</Carte>}>
          <Anneaux analytique={analytique} />
        </Suspense>
      </div>

      <Kpis items={[
        { nom: 'Encours clients', v: court(k.encours_clients), progres: k.pct_limite_encours, sous: `${pct(k.pct_limite_encours)} de la limite 30 MMAD` },
        { nom: 'Clients actifs', v: entier(k.nb_clients_actifs), sous: 'au moins une facture de vente' },
        { nom: 'Panier moyen', v: pm?.panier_moyen == null ? 'N/A' : `${entier(Math.round(pm.panier_moyen))} MAD`,
          sous: pm?.evolution_pct == null ? 'CA HT ÷ factures' : (
            <span className={pm.evolution_pct < 0 ? 'mauvais fort' : 'bon fort'} title={`${annees(t.historique[0].du, t.historique[0].au)} : ${entier(Math.round(pm.panier_moyen_n1))} MAD sur ${entier(pm.factures_n1)} factures`}>
              {pm.evolution_pct < 0 ? '▼' : '▲'} {pct(pm.evolution_pct, true)} vs {annees(t.historique[0].du, t.historique[0].au)}
            </span>
          ) },
        { nom: 'Total achats', v: court(k.total_achats) },
        { nom: 'Valeur du stock', v: court(k.valeur_stock) },
        { nom: 'Dettes fournisseurs', v: court(k.dettes_fournisseurs),
          progres: k.pct_limite_dettes, sous: k.pct_limite_dettes == null ? undefined : `${pct(k.pct_limite_dettes)} de la limite 20 MMAD` },
      ]} />

      <div className="grille">
        <Suspense fallback={<Carte titre="Progression du CA HT">{ATTENTE}</Carte>}>
          <ProgressionCA ventes={ventes} objectif={du.slice(0, 4) === au.slice(0, 4) ? OBJECTIF_CA : null} p={p} du={du} au={au} client={s.client} />
        </Suspense>
        <Suspense fallback={<Carte titre="Classements">{ATTENTE}</Carte>}>
          <Classements analytique={analytique} plus={plus} p={p} collab={collab} />
        </Suspense>
      </div>
    </Page>
  )
}
