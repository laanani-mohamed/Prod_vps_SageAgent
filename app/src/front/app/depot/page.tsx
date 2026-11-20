import DepotFichiers from '../../components/DepotFichiers'
import Page from '../../components/Page'
import { Entete, Interdit } from '../../components/ui'
import { api, estCollaborateur, session } from '../../lib/api'

/** Dépôt des fichiers Sage : réservé au directeur (l'envoi remplace toutes les données du client). */
export default async function Depot() {
  const s = await session()
  const etat = estCollaborateur(s) ? null : await api(`/api/depot/etat?client_schema=${encodeURIComponent(s.client ?? '')}`)
  return (
    <Page theme="depot">
      {etat ? <DepotFichiers initial={etat} /> : <><Entete titre="Dépôt des fichiers Sage" /><Interdit /></>}
    </Page>
  )
}
