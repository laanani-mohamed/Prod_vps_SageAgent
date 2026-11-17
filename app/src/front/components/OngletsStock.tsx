import { Onglets } from './ui'

export const ONGLETS_STOCK = { etat: 'État des stocks', entrants: 'Mouvements entrants', sortants: 'Mouvements sortants', alertes: 'Alertes & insights', plan: 'Plan des dépôts' }

export default function OngletsStock({ actif }: { actif: string }) {
  return <Onglets items={Object.entries(ONGLETS_STOCK).map(([c, nom]) => ({ nom, href: `/stock/${c}`, actif: c === actif }))} />
}
