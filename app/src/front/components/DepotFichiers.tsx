'use client'

// Dépôt des fichiers Sage (directeur) : réception des 11 exports, envoi au traitement ETL, suivi du chargement.
// Tout passe par le relais app/depot/api → /api/depot/* (api/depot/router.py), qui contrôle aussi les noms.
import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import { dateHeure } from '../lib/format'
import { Telecharger } from './Interactions'

type Recu = { nom: string; taille: number; recu_le: string }
type Erreur = { code: string | null; rapport: boolean; fichier: string | null; ligne: string | null; colonne: string | null; probleme: string | null; que_faire: string | null }
type Chargement = { run_id: string; debut: string; fin: string; statut: 'en_cours' | 'reussi' | 'echec'; etapes: (string | null)[]; echec: number | null; erreur: Erreur | null }
export type EtatDepot = { dossier: string; attendus: string[]; recus: Recu[]; sftp: number; en_file: boolean; dernier: Chargement | null; dernier_reussi: string | null }

const RELAIS = '/depot/api'
const ETAPES = ['Fichiers envoyés', 'Pris en charge par le traitement', 'Contrôle des fichiers', 'Chargement des données', 'Terminé : données à jour']
const ICONE_DEPOT = 'M12 15V4M7 9l5-5 5 5M4 15v5h16v-5'
const fr = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
const taille = (o: number) => (o >= 1e6 ? `${fr(o / 1e6)} Mo` : o >= 1e3 ? `${fr(o / 1e3)} Ko` : `${o} o`)
const heure = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString('fr-FR', { timeZone: 'UTC' }) : '')
const pluriel = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`

function Icone({ d, taille = 16 }: { d: string; taille?: number }) {
  return <svg aria-hidden="true" width={taille} height={taille} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={d} /></svg>
}

/** Envoi d'un fichier (corps brut, avec progression) ; résout le message d'erreur, ou null si reçu. */
function televerser(nom: string, f: File, progres: (pct: number) => void) {
  return new Promise<string | null>((fini) => {
    const x = new XMLHttpRequest()
    x.open('PUT', `${RELAIS}/fichiers/${encodeURIComponent(nom)}`)
    x.upload.onprogress = (e) => e.lengthComputable && progres(Math.floor((e.loaded / e.total) * 100))
    x.onload = () => fini(x.status < 300 ? null : x.status === 401 ? 'Session expirée : rechargez la page puis déposez à nouveau.' : `${nom} : envoi refusé par le serveur (${x.status}).`)
    x.onerror = () => fini(`${nom} : envoi interrompu (connexion perdue).`)
    x.send(f)
  })
}

export default function DepotFichiers({ initial }: { initial: EtatDepot }) {
  const router = useRouter()
  const [etat, setEtat] = useState(initial)
  const [envois, setEnvois] = useState<Record<string, number | 'attente'>>({})   // nom → % envoyé
  const [refuses, setRefuses] = useState<{ nom: string; motif: string }[]>([])
  const [envoiLe, setEnvoiLe] = useState<string | null>(null)   // envoi au traitement fait depuis cette page
  const [envoi, setEnvoi] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [survol, setSurvol] = useState(false)
  const choix = useRef<HTMLInputElement>(null)

  const { dossier, attendus, dernier: d } = etat
  const recus = new Map(etat.recus.map((r) => [r.nom, r]))
  const prets = attendus.filter((n) => recus.has(n) && envois[n] === undefined).length
  const attente = etat.sftp > 0 || etat.en_file   // fichiers vus par l'ETL, pas encore traités
  const courant = d && !(envoiLe && d.debut < envoiLe) ? d : null   // un chargement antérieur à l'envoi ne compte plus
  const enCours = attente || courant?.statut === 'en_cours'
  const echec = !enCours && courant?.statut === 'echec' ? courant : null
  const libre = !etat.en_file
  const controles: [boolean, string, string][] = [
    [prets === attendus.length, `${attendus.length} fichiers avec un nom valide`,
      prets === attendus.length ? 'tous les fichiers attendus sont reçus' : `${attendus.length - prets} manquant${attendus.length - prets > 1 ? 's' : ''} ou en cours d'envoi`],
    [etat.sftp === 0, 'Aucun dépôt SFTP en cours',
      etat.sftp === 0 ? `le dossier ${dossier} ne contient pas d'autres fichiers` : `le dossier ${dossier} contient ${pluriel(etat.sftp, 'fichier')} en attente de traitement`],
    [libre, 'Aucun chargement en cours', libre ? 'le traitement est disponible' : 'attendez la fin du chargement en cours'],
  ]
  const pret = controles.every(([ok]) => ok) && !envoi && Object.keys(envois).length === 0

  async function actualiser() {
    const r = await fetch(`${RELAIS}/etat`, { cache: 'no-store' }).catch(() => null)
    if (r?.ok && !r.redirected) setEtat(await r.json())
    else setMessage(r?.redirected || r?.status === 401 ? 'Session expirée : rechargez la page.' : 'État du dépôt indisponible : nouvel essai dans un instant.')
  }

  // Suivi automatique tant que l'ETL n'a pas fini ; à la fin, menu (« Dernière mise à jour ») rafraîchi
  useEffect(() => {
    if (!enCours) return
    const minuteur = setInterval(actualiser, 4000)
    return () => clearInterval(minuteur)
  }, [enCours])
  useEffect(() => {
    if (envoiLe && courant?.statut === 'reussi') router.refresh()
  }, [envoiLe, courant?.statut, router])

  async function deposer(liste: FileList | null) {
    if (!liste?.length) return
    setMessage(null)
    const parNom = new Map(attendus.map((n) => [n.toUpperCase(), n]))
    const acceptes = [...liste].flatMap((f) => (parNom.has(f.name.toUpperCase()) ? [[parNom.get(f.name.toUpperCase())!, f] as const] : []))
    const refus = [...liste].filter((f) => !parNom.has(f.name.toUpperCase()))
      .map((f) => ({ nom: f.name, motif: /\(\d+\)/.test(f.name) ? 'copie renommée (« (1) » ajouté au nom)' : 'aucun nom attendu ne correspond' }))
    setRefuses((r) => [...r.filter((x) => !refus.some((y) => y.nom === x.nom)), ...refus])
    setEnvois((e) => ({ ...e, ...Object.fromEntries(acceptes.map(([n]) => [n, 'attente'])) }))
    await actualiser()   // jeton de session renouvelé au besoin avant les envois
    for (const [nom, f] of acceptes) {   // un fichier à la fois
      const erreur = await televerser(nom, f, (pct) => setEnvois((e) => ({ ...e, [nom]: pct })))
      if (erreur) setMessage(erreur)
      else await actualiser()
      setEnvois(({ [nom]: _, ...reste }) => reste)
    }
  }

  async function retirer(nom: string) {
    const r = await fetch(`${RELAIS}/fichiers/${encodeURIComponent(nom)}`, { method: 'DELETE' }).catch(() => null)
    if (!r?.ok) setMessage(`${nom} n'a pas pu être retiré.`)
    await actualiser()
  }

  async function envoyer() {
    if (!pret) return
    setEnvoi(true)
    setMessage(null)
    const r = await fetch(`${RELAIS}/envoyer`, { method: 'POST' }).catch(() => null)
    const corps = await r?.json().catch(() => null)
    if (r?.ok) {
      setEnvoiLe(corps.envoye_le)
      setRefuses([])
    } else setMessage(`Envoi impossible : ${corps?.detail ?? 'serveur injoignable'}.`)
    await actualiser()
    setEnvoi(false)
  }

  // Étapes du suivi : envoi en attente de l'ETL, chargement en cours, réussi ou arrêté sur une erreur
  const suivi = attente && courant?.statut !== 'en_cours'
    ? ETAPES.map((nom, k) => ({ nom, classe: k === 0 ? 'fait' : k === 1 ? 'courant' : '', heure: k === 0 ? envoiLe : null }))
    : courant && (envoiLe || courant.statut !== 'reussi')
      ? ETAPES.map((nom, k) => {
          const h = k === 0 ? envoiLe : courant.etapes[k], e = courant.echec
          if (e != null) return { nom: k === e ? `${nom} : erreur trouvée` : k > e ? `${nom} (non effectué)` : nom, classe: k < e ? 'fait' : k === e ? 'echec' : '', heure: h }
          const fait = k === 0 || !!courant.etapes[k]
          return { nom, classe: fait ? 'fait' : k === courant.etapes.findIndex((x, i) => i > 0 && !x) ? 'courant' : '', heure: h }
        })
      : null
  const er = echec?.erreur

  return (
    <>
      <header className="entete">
        <div>
          <h1>Dépôt des fichiers Sage</h1>
          <p className="doux">Déposez les {attendus.length} exports Sage de {dossier} puis envoyez-les au traitement. Ils remplacent toutes les données actuelles du tableau de bord.</p>
        </div>
        <div className="infos-depot">
          <span className="info-depot"><span className="doux">Dossier</span><strong>{dossier}</strong></span>
          <span className="info-depot">
            <span className={`point ${d?.statut ?? ''}`} aria-hidden="true" />
            <span className="doux">Dernier chargement</span>
            <strong>{d ? `${dateHeure(d.fin)} · ${{ reussi: 'réussi', echec: 'échec', en_cours: 'en cours' }[d.statut]}` : 'aucun'}</strong>
          </span>
        </div>
      </header>

      {message && <p role="alert" className="vide mauvais">{message}</p>}

      {echec && (
        <section className="echec-depot" role="alert" aria-labelledby="depot-echec">
          <span className="signe" aria-hidden="true">!</span>
          <div className="corps">
            <div>
              <h2 id="depot-echec">Le chargement du {dateHeure(echec.fin)} a échoué</h2>
              <p className="rassure">
                Vos données actuelles n&apos;ont pas été modifiées{etat.dernier_reussi ? ` : le tableau de bord affiche toujours le chargement du ${dateHeure(etat.dernier_reussi)}` : ''}.
              </p>
            </div>
            {(er?.fichier || er?.ligne || er?.colonne) && (
              <div className="cases">
                {([['Fichier concerné', er.fichier], ['Ligne concernée', er.ligne], ['Colonne concernée', er.colonne]] as const).map(([t, v]) => (
                  <div key={t}><div className="petit doux">{t}</div><strong>{v ?? '—'}</strong></div>
                ))}
              </div>
            )}
            <p><strong>Problème :</strong> {er?.probleme ?? `le traitement a refusé les fichiers (code ${er?.code ?? 'inconnu'}).`}</p>
            <p><strong>Que faire :</strong> {er?.que_faire ?? 'contactez votre support technique en indiquant la référence ci-dessous.'}</p>
            <div className="pied">
              <span className="petit doux">Référence pour le support : <code>{echec.run_id}</code></span>
              <span className="actions">
                {er?.rapport && (
                  <Telecharger href={`${RELAIS}/rapport?run_id=${echec.run_id}`} className="secondaire">
                    <Icone d="M12 4v11M7 10l5 5 5-5M5 20h14" taille={15} />Télécharger le rapport d&apos;erreur
                  </Telecharger>
                )}
                <button type="button" className="principal" onClick={() => choix.current?.click()}>Déposer les fichiers corrigés</button>
              </span>
            </div>
          </div>
        </section>
      )}

      <div className="depot-grille">
        <section className="carte" aria-labelledby="depot-fichiers">
          <div className="carte-titre"><h2 id="depot-fichiers">1 · Fichiers</h2><span className="doux">{prets} reçu{prets > 1 ? 's' : ''} sur {attendus.length}</span></div>
          {echec && <p className="note-depot">Après l&apos;échec, les fichiers envoyés ont été mis de côté. Déposez à nouveau les {attendus.length} fichiers, une fois l&apos;export corrigé.</p>}

          <div className={`zone-depot${survol ? ' survol' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setSurvol(true) }} onDragLeave={() => setSurvol(false)}
            onDrop={(e) => { e.preventDefault(); setSurvol(false); deposer(e.dataTransfer.files) }}>
            <span className="icone-depot"><Icone d={ICONE_DEPOT} taille={26} /></span>
            <div>
              <div className="fort">Glissez les fichiers ici</div>
              <div className="petit doux">Plusieurs fichiers à la fois · le nom doit être l&apos;un des {attendus.length} noms attendus (majuscules ou minuscules acceptées)</div>
            </div>
            <button type="button" className="principal" onClick={() => choix.current?.click()}>Parcourir…</button>
            <input ref={choix} type="file" multiple accept=".txt" hidden onChange={(e) => { deposer(e.target.files); e.target.value = '' }} />
          </div>

          <table className="fichiers-depot">
            <thead><tr><th><span className="sr-only">Reçu</span></th><th>Fichier attendu</th><th>État</th><th className="droite">Taille</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>
              {attendus.map((nom) => {
                const r = recus.get(nom), e = envois[nom]
                const recuLe = r && (dateHeure(r.recu_le).slice(0, 10) === dateHeure(new Date().toISOString()).slice(0, 10) ? `à ${heure(r.recu_le).slice(0, 5)}` : `le ${dateHeure(r.recu_le)}`)
                return (
                  <tr key={nom} className={!r && e === undefined ? 'manquant' : ''}>
                    <td><span className={`rond ${e !== undefined ? 'envoi' : r ? 'ok' : ''}`} aria-hidden="true">{r && e === undefined ? '✓' : ''}</span></td>
                    <td className="fort">{nom}</td>
                    <td>
                      {typeof e === 'number' ? (
                        <span className="barre-envoi">
                          <span className="jauge" role="progressbar" aria-label={`Envoi de ${nom}`} aria-valuenow={e} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${e}%` }} /></span>
                          <span className="petit doux">{e} %</span>
                        </span>
                      ) : e === 'attente' ? <span className="doux">En attente d&apos;envoi…</span>
                        : r ? <span>Reçu {recuLe}</span> : <span className="manque">Manquant</span>}
                    </td>
                    <td className="droite doux">{r ? taille(r.taille) : '—'}</td>
                    <td className="droite">
                      {r && e === undefined && !enCours && (
                        <button type="button" className="retirer" onClick={() => retirer(nom)} aria-label={`Retirer ${nom}`}><Icone d="M6 6l12 12M18 6L6 18" taille={14} /></button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {refuses.length > 0 && (
            <div className="refus-depot" role="status">
              <div className="titre">Fichiers refusés : nom non reconnu</div>
              {refuses.map((r) => (
                <div key={r.nom} className="ligne">
                  <span><strong>{r.nom}</strong> <span className="doux">· {r.motif}</span></span>
                  <button type="button" className="secondaire petit-bouton" onClick={() => setRefuses(refuses.filter((x) => x.nom !== r.nom))}>Ignorer</button>
                </div>
              ))}
              <div className="petit doux">Renommez le fichier avec l&apos;un des noms attendus, puis déposez-le à nouveau.</div>
            </div>
          )}
        </section>

        <section className="carte" aria-labelledby="depot-envoi">
          <div className="carte-titre"><h2 id="depot-envoi">2 · Envoi au traitement</h2></div>
          <div className="compteur-depot"><strong>{prets}</strong><span className="doux">/ {attendus.length} fichiers prêts</span></div>
          <span className="jauge" aria-hidden="true"><span style={{ width: `${(prets / attendus.length) * 100}%` }} /></span>
          <ul className="controles-depot">
            {controles.map(([ok, titre, detail]) => (
              <li key={titre}>
                <span className={`marque-controle${ok ? ' ok' : ''}`} aria-hidden="true">{ok ? '✓' : '!'}</span>
                <span><strong>{titre}</strong><span className="doux">{detail}</span></span>
              </li>
            ))}
          </ul>
          <p className="note-depot">
            L&apos;envoi remplace toutes les données de {dossier}. Les fichiers sont ensuite contrôlés en détail par le traitement automatique ; en cas d&apos;erreur, le motif s&apos;affiche en haut de cette page.
          </p>
          <button type="button" className="principal large envoyer" onClick={envoyer} disabled={!pret} aria-busy={envoi}>
            {envoi && <span className="cercle" aria-hidden="true" />}
            {envoi ? 'Envoi en cours…' : enCours ? 'Chargement en cours…' : pret ? 'Envoyer au traitement' : `Envoyer au traitement (${prets}/${attendus.length})`}
          </button>

          {suivi && (
            <div className="suivi-depot" aria-live="polite">
              <h3>Suivi du chargement</h3>
              <ol>
                {suivi.map((e) => (
                  <li key={e.nom} className={e.classe}>
                    <span className="rond-etape" aria-hidden="true">{e.classe === 'fait' ? '✓' : e.classe === 'echec' ? '!' : e.classe === 'courant' ? '…' : ''}</span>
                    <span>{e.nom}</span>
                    <span className="heure">{heure(e.heure)}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      </div>
    </>
  )
}
