import Page from '../../../components/Page'
import PlanDepots from '../../../components/PlanDepots'
import OngletsStock from '../../../components/OngletsStock'
import { Entete, Interdit } from '../../../components/ui'
import { estCollaborateur, session, vue } from '../../../lib/api'

export default async function PlanDesDepots() {
  const collab = estCollaborateur(await session())
  return (
    <Page accent="#f35b04">
      <Entete titre="Stock & Mouvements" sousTitre="Plan des dépôts : une section par famille, étagères remplies selon la quantité en stock" />
      <OngletsStock actif="plan" />
      {collab ? <Interdit /> : <PlanDepots {...(await vue('plan_depots'))} />}
    </Page>
  )
}
