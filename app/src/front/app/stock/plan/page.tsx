import Page from '../../../components/Page'
import PlanDepots from '../../../components/PlanDepots'
import OngletsStock from '../../../components/OngletsStock'
import { Entete, Interdit } from '../../../components/ui'
import { estCollaborateur, session, vue } from '../../../lib/api'

export default async function PlanDesDepots() {
  const collab = estCollaborateur(await session())
  return (
    <Page accent="#467599">
      <Entete titre="Stock & Mouvements" sousTitre="Plan des dépôts : de quoi le stock est rempli, tous dépôts confondus ou dépôt par dépôt" />
      <OngletsStock actif="plan" />
      {collab ? <Interdit /> : <PlanDepots {...(await vue('plan_depots'))} />}
    </Page>
  )
}
