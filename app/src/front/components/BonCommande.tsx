'use client'

// Page « Passer bon de commande » (page 9 de Streamlit). La recherche d'articles passe par l'URL (formulaire GET,
// page rendue côté serveur) ; le brouillon (client, lignes, remises) reste dans le navigateur, comme la session
// Streamlit, et le PDF est généré par l'API (prix relus dans Sage). Rien n'est écrit en base.
import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { entier, mad } from '../lib/format'
import { FormulaireGet } from './Interactions'
import { Entete } from './ui'

export type ArticleTrouve = { ar_ref: string; ar_design: string | null; fa_codefamille: string | null; ar_prixven: number | null; qte_stock_totale: number | null }
type Ligne = { ref: string; famille: string; design: string; pu: number; stock: number; qte: number; remise: number }
type Client = { ct_num: string; ct_intitule: string | null }

const TVA = 20
const borne = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v))
const nombre = (texte: string, defaut: number) => {
  const n = parseFloat(texte.replace(',', '.'))
  return Number.isFinite(n) ? n : defaut
}
const montant = (l: Ligne) => l.pu * l.qte * (1 - l.remise / 100)

export default function BonCommande({ schema, clients, familles, articles, total, filtres }: {
  schema: string
  clients: Client[]
  familles: { code: string; nom: string }[]
  articles: ArticleTrouve[] | null   // null : aucune recherche lancée
  total: number
  filtres: { familles: string[]; ref: string; design: string }
}) {
  const cle = `bon-commande:${schema}`
  const [client, setClient] = useState('')
  const [saisie, setSaisie] = useState('')
  const [lignes, setLignes] = useState<Ligne[]>([])
  const [remiseG, setRemiseG] = useState(0)
  const [relu, setRelu] = useState(false)
  const [selection, setSelection] = useState<string[]>([])
  const [choixFamilles, setChoixFamilles] = useState(filtres.familles)
  const [saisieFamille, setSaisieFamille] = useState('')
  const [pdf, setPdf] = useState<'pret' | 'encours' | 'fait' | 'echec'>('pret')

  // Brouillon gardé dans ce navigateur (rechargement, autre onglet) ; illisible ou bloqué → brouillon vide.
  useEffect(() => {
    try {
      const b = JSON.parse(localStorage.getItem(cle) ?? 'null')
      if (b) { setClient(b.client ?? ''); setSaisie(b.client ?? ''); setLignes(b.lignes ?? []); setRemiseG(b.remiseG ?? 0) }
    } catch { /* brouillon vide */ }
    setRelu(true)
  }, [cle])
  useEffect(() => {
    if (!relu) return
    try { localStorage.setItem(cle, JSON.stringify({ client, lignes, remiseG })) } catch { /* non enregistré */ }
  }, [relu, cle, client, lignes, remiseG])

  const parCode = useMemo(() => new Map(clients.map((c) => [c.ct_num, c])), [clients])
  const nomFamille = useMemo(() => new Map(familles.map((f) => [f.code, f.nom])), [familles])
  const dansBon = new Set(lignes.map((l) => l.ref))
  const choisis = selection.filter((r) => !dansBon.has(r))
  const leClient = parCode.get(client)

  const brut = lignes.reduce((s, l) => s + montant(l), 0)
  const ht = brut * (1 - remiseG / 100)
  const avantRemise = lignes.reduce((s, l) => s + l.pu * l.qte, 0)
  const tva = ht * (TVA / 100)
  const unites = lignes.reduce((s, l) => s + l.qte, 0)
  const depasse = lignes.some((l) => l.qte > l.stock)
  const qteManquante = lignes.some((l) => !(l.qte > 0))
  const bloquant = !client ? 'Choisissez un client pour générer le PDF.'
    : qteManquante ? 'Indiquez une quantité pour chaque ligne.' : ''

  function choisirClient(v: string) {
    setSaisie(v)
    const t = v.trim()
    const c = parCode.get(t) ?? clients.find((x) => (x.ct_intitule ?? '').toLowerCase() === t.toLowerCase())
    setClient(c ? c.ct_num : '')
  }
  function ajouterFamille(v: string) {
    setSaisieFamille(v)
    if (nomFamille.has(v) && !choixFamilles.includes(v)) { setChoixFamilles([...choixFamilles, v]); setSaisieFamille('') }
  }
  function ajouter() {
    const nouvelles = (articles ?? []).filter((a) => choisis.includes(a.ar_ref)).map((a): Ligne => ({
      ref: a.ar_ref, famille: a.fa_codefamille ?? '', design: a.ar_design ?? '',
      pu: a.ar_prixven ?? 0, stock: a.qte_stock_totale ?? 0, qte: 1, remise: 0,
    }))
    setLignes([...lignes, ...nouvelles])
    setSelection([])
  }
  const changer = (ref: string, champs: Partial<Ligne>) => setLignes(lignes.map((l) => (l.ref === ref ? { ...l, ...champs } : l)))

  async function telecharger() {
    if (pdf === 'encours' || bloquant || !lignes.length) return
    setPdf('encours')
    try {
      const r = await fetch('/bon-de-commande/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ct_num: client, remise_globale: remiseG, lignes: lignes.map((l) => ({ ar_ref: l.ref, qte: l.qte, remise_pct: l.remise })) }),
      })
      if (!r.ok) throw new Error(String(r.status))
      const nom = /filename="([^"]+)"/.exec(r.headers.get('content-disposition') ?? '')?.[1] ?? 'bon_de_commande.pdf'
      const url = URL.createObjectURL(await r.blob())
      Object.assign(document.createElement('a'), { href: url, download: nom }).click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setPdf('fait')
      setTimeout(() => setPdf('pret'), 2500)
    } catch {
      setPdf('echec')
    }
  }

  const faites = [!!client, lignes.length > 0, false]
  const etapes = ['Client', 'Articles', 'Bon de commande'].map((nom, i) => ({
    nom, faite: faites[i], courante: !faites[i] && faites.slice(0, i).every(Boolean),
  }))
  const pluriel = (n: number, mot: string) => `${entier(n)} ${mot}${n > 1 ? 's' : ''}`

  return <>
    <Entete titre="Nouveau Bon de Commande" sousTitre="Choisissez le client, ajoutez les articles du catalogue Sage, puis téléchargez le bon en PDF"
      actions={
        <ol className="etapes" aria-label="Étapes">
          {etapes.map((e, i) => (
            <li key={e.nom} className={e.faite ? 'faite' : e.courante ? 'courante' : undefined} aria-current={e.courante ? 'step' : undefined}>
              <span className="rond" aria-hidden="true">{e.faite ? '✓' : i + 1}</span>{e.nom}{e.faite && <span className="sr"> (fait)</span>}
            </li>
          ))}
        </ol>
      } />

    <section className="carte" aria-labelledby="bc-client-titre">
      <div className="carte-titre"><h2 id="bc-client-titre">1 · Client</h2><span className="doux">{pluriel(clients.length, 'compte')} client{clients.length > 1 ? 's' : ''}</span></div>
      <div className="choix-client">
        <label className="champ-filtre">
          <span>Client (code ou raison sociale)</span>
          <input list="bc-clients" value={saisie} onChange={(e) => choisirClient(e.target.value)} placeholder="Rechercher un client…" autoComplete="off" />
        </label>
        <datalist id="bc-clients">
          {clients.map((c) => <option key={c.ct_num} value={c.ct_num}>{c.ct_intitule}</option>)}
        </datalist>
        <div className="info-case"><span className="doux">Raison sociale</span><strong className="coupe" title={leClient?.ct_intitule ?? undefined}>{leClient?.ct_intitule ?? '—'}</strong></div>
        <div className="info-case"><span className="doux">Date du bon</span><strong>{new Date().toLocaleDateString('fr-FR')}</strong></div>
      </div>
      {saisie && !client && <p className="doux petit" role="status">Aucun client ne correspond : choisissez-le dans la liste.</p>}
    </section>

    <section className="carte" aria-labelledby="bc-articles-titre">
      <div className="carte-titre"><h2 id="bc-articles-titre">2 · Articles</h2>{articles && <span className="doux">{pluriel(total, 'article')} trouvé{total > 1 ? 's' : ''}</span>}</div>
      <FormulaireGet className="filtres recherche-articles">
        <input type="hidden" name="familles" value={choixFamilles.join(',')} />
        <div className="champ-filtre">
          <span id="bc-familles-titre">Familles</span>
          <div className="puces-familles" role="group" aria-labelledby="bc-familles-titre">
            {choixFamilles.map((code) => (
              <span key={code} className="puce-famille">
                {code}{nomFamille.get(code) ? ` · ${nomFamille.get(code)}` : ''}
                <button type="button" onClick={() => setChoixFamilles(choixFamilles.filter((c) => c !== code))} aria-label={`Retirer la famille ${code}`}>
                  <svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M6 6l12 12M18 6L6 18" /></svg>
                </button>
              </span>
            ))}
            <input list="bc-familles" value={saisieFamille} onChange={(e) => ajouterFamille(e.target.value)}
              placeholder={choixFamilles.length ? 'Ajouter…' : 'Toutes — ajouter une famille…'} aria-label="Ajouter une famille" autoComplete="off" />
          </div>
          <datalist id="bc-familles">{familles.map((f) => <option key={f.code} value={f.code}>{f.nom}</option>)}</datalist>
        </div>
        <label className="champ-filtre"><span>Réf. article contient</span><input name="ref" defaultValue={filtres.ref} placeholder="ex : AM03" /></label>
        <label className="champ-filtre"><span>Désignation contient</span><input name="design" defaultValue={filtres.design} placeholder="ex : AMORTISSEUR" /></label>
        <button type="submit" className="principal">Rechercher</button>
      </FormulaireGet>

      {articles === null ? <p className="vide">Choisissez une famille ou saisissez une recherche pour afficher des articles.</p>
        : !articles.length ? <p className="vide">Aucun article ne correspond à cette recherche.</p>
        : <>
          <p className="doux petit">Cochez un ou plusieurs articles puis ajoutez-les d&apos;un coup : la quantité se règle dans le bon de commande.</p>
          <div className="defile resultats">
            <table className="tableau">
              <colgroup><col style={{ width: 44 }} /><col style={{ width: 130 }} /><col /><col style={{ width: 100 }} /><col style={{ width: 110 }} /><col style={{ width: 80 }} /><col style={{ width: 120 }} /></colgroup>
              <thead><tr><th aria-label="Sélection" /><th>Réf. Article</th><th>Désignation</th><th>Famille</th><th className="droite">PU HT</th><th className="droite">Stock</th><th /></tr></thead>
              <tbody>
                {articles.map((a) => {
                  const dedans = dansBon.has(a.ar_ref)
                  const coche = dedans || selection.includes(a.ar_ref)
                  return (
                    <tr key={a.ar_ref} className={coche && !dedans ? 'actif' : undefined}>
                      <td><input type="checkbox" className="coche" checked={coche} disabled={dedans} aria-label={`Sélectionner l'article ${a.ar_ref}`}
                        onChange={() => setSelection(selection.includes(a.ar_ref) ? selection.filter((r) => r !== a.ar_ref) : [...selection, a.ar_ref])} /></td>
                      <td className="fort">{a.ar_ref}</td>
                      <td title={a.ar_design ?? ''}>{a.ar_design}</td>
                      <td>{a.fa_codefamille}</td>
                      <td className="droite">{mad(a.ar_prixven)}</td>
                      <td className="droite">{entier(a.qte_stock_totale)}</td>
                      <td className="droite">{dedans && <span className="puce verte">dans le bon</span>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="actions-bon">
            <span className="doux petit">
              {total > articles.length && `${entier(articles.length)} premiers sur ${entier(total)} : affinez la recherche. `}
              {choisis.length ? `${pluriel(choisis.length, 'article')} sélectionné${choisis.length > 1 ? 's' : ''}` : 'Aucun article sélectionné'}
            </span>
            <button type="button" className="bouton-vert" onClick={ajouter} disabled={!choisis.length}>
              <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
              {!choisis.length ? 'Cochez des articles à ajouter' : choisis.length === 1 ? `Ajouter « ${choisis[0]} »` : `Ajouter les ${choisis.length} articles sélectionnés`}
            </button>
          </div>
        </>}
    </section>

    <section className="carte" aria-labelledby="bc-bon-titre">
      <div className="carte-titre"><h2 id="bc-bon-titre">3 · Bon de commande</h2><span className="doux">{pluriel(lignes.length, 'article')} · {pluriel(unites, 'unité')}</span></div>
      {!lignes.length ? <p className="vide">Aucun article dans le bon de commande.</p> : <>
        <div className="defile">
          <table className="tableau panier">
            <colgroup><col style={{ width: 48 }} /><col style={{ width: 84 }} /><col style={{ width: 110 }} /><col /><col style={{ width: 100 }} /><col style={{ width: 80 }} /><col style={{ width: 160 }} /><col style={{ width: 90 }} /><col style={{ width: 112 }} /></colgroup>
            <thead><tr><th aria-label="Retirer" /><th>Famille</th><th>Réf. Article</th><th>Désignation</th><th className="droite">PU HT</th><th className="droite">Qté max</th><th>Qté</th><th>Remise %</th><th className="droite">Montant HT</th></tr></thead>
            <tbody>
              {lignes.map((l) => (
                <tr key={l.ref} className={l.qte > l.stock ? 'trop' : undefined}>
                  <td><button type="button" className="icone-suppr" onClick={() => setLignes(lignes.filter((x) => x.ref !== l.ref))} aria-label={`Retirer ${l.ref} du bon de commande`}>
                    <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>
                  </button></td>
                  <td>{l.famille}</td>
                  <td className="fort">{l.ref}</td>
                  <td title={l.design}>{l.design}</td>
                  <td className="droite">{mad(l.pu)}</td>
                  <td className="droite">{entier(l.stock)}</td>
                  <td>
                    <span className="quantite">
                      <button type="button" onClick={() => changer(l.ref, { qte: Math.max(1, l.qte - 1) })} aria-label={`Diminuer la quantité de ${l.ref}`}>−</button>
                      <input type="number" min={0} step={1} value={l.qte || ''} aria-label={`Quantité de ${l.ref}`} aria-invalid={l.qte > l.stock || !(l.qte > 0)}
                        onChange={(e) => changer(l.ref, { qte: e.target.value === '' ? 0 : borne(nombre(e.target.value, l.qte), 0, 1_000_000) })} />
                      <button type="button" onClick={() => changer(l.ref, { qte: l.qte + 1 })} aria-label={`Augmenter la quantité de ${l.ref}`}>+</button>
                    </span>
                  </td>
                  <td><input className="remise" type="number" min={0} max={100} step={1} value={l.remise} aria-label={`Remise en % de ${l.ref}`}
                    onChange={(e) => changer(l.ref, { remise: borne(nombre(e.target.value, 0), 0, 100) })} /></td>
                  <td className="droite fort">{mad(montant(l))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <label className="remise-globale">Remise globale sur le total (%)
          <input type="number" min={0} max={100} step={1} value={remiseG} onChange={(e) => setRemiseG(borne(nombre(e.target.value, 0), 0, 100))} />
        </label>

        <div className="kpis" style={{ '--n': 4 } as CSSProperties}>
          <div className="kpi"><div className="doux">Montant remisé</div><div className="valeur">{mad(avantRemise - ht)}</div></div>
          <div className="kpi"><div className="doux">Total HT</div><div className="valeur">{mad(ht)}</div></div>
          <div className="kpi"><div className="doux">TVA {TVA} %</div><div className="valeur">{mad(tva)}</div></div>
          <div className="kpi total-ttc"><div className="doux">Total TTC</div><div className="valeur">{mad(ht + tva)} DH</div></div>
        </div>

        {depasse && (
          <div className="avertissement" role="status">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></svg>
            Certaines quantités dépassent le stock disponible (lignes en rouge). Le bon de commande peut tout de même être généré.
          </div>
        )}

        <div className="actions-bon">
          <span className="doux petit">{bloquant || <>Fichier : <strong>{client}_{new Date().toISOString().slice(0, 10)}.pdf</strong></>}</span>
          <span className="actions-bon">
            <button type="button" className="secondaire" onClick={() => { setLignes([]); setRemiseG(0); setPdf('pret') }}>Vider le bon</button>
            <button type="button" className={pdf === 'fait' ? 'principal reussi' : 'principal'} onClick={telecharger}
              disabled={!!bloquant || pdf === 'encours'} aria-busy={pdf === 'encours'}>
              {pdf === 'encours' ? <span className="cercle" aria-hidden="true" />
                : <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={pdf === 'fait' ? 'M5 12l5 5L20 7' : 'M12 4v11M7 10l5 5 5-5M5 20h14'} /></svg>}
              {{ pret: 'Télécharger le bon de commande (PDF)', encours: 'Génération du PDF…', fait: 'Bon de commande téléchargé', echec: 'Échec — réessayer' }[pdf]}
            </button>
          </span>
        </div>
      </>}
    </section>
  </>
}
