import BonCommande, { type ArticleTrouve } from '../../components/BonCommande'
import Page from '../../components/Page'
import { api, session, vue } from '../../lib/api'
import { lire, type Params } from '../../lib/params'

/** Passer bon de commande : clients et familles pour les listes de choix ; articles seulement après une recherche. */
export default async function PasserBonDeCommande({ searchParams }: { searchParams: Promise<Params> }) {
  const p = await searchParams
  const s = await session()
  const filtres = { familles: lire(p, 'familles').split(',').filter(Boolean), ref: lire(p, 'ref'), design: lire(p, 'design') }
  const recherche = filtres.familles.length > 0 || !!filtres.ref || !!filtres.design
  const [clients, familles, articles] = await Promise.all([
    vue('clients'),
    api('/api/referentiel/familles', { client_schema: s.client }),
    recherche ? vue<{ lignes: ArticleTrouve[]; total: number }>('articles', { ...filtres, familles: filtres.familles.join(','), taille: 200 }) : null,
  ])
  return (
    <Page theme="commande">
      <BonCommande
        schema={s.client ?? ''}
        clients={clients?.clients ?? []}
        familles={(familles?.data ?? []).map((f: any) => ({ code: f.fa_codefamille, nom: f.fa_intitule ?? '' }))}
        articles={articles ? articles.lignes : null}
        total={articles?.total ?? 0}
        filtres={filtres}
      />
    </Page>
  )
}
