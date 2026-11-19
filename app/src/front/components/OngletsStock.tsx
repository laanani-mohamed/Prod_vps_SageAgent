import { Onglets } from './ui'

export const ONGLETS_STOCK = { plan: 'Plan des dépôts', etat: 'État des stocks', alertes: 'Alertes & insights', entrants: 'Mouvements entrants', sortants: 'Mouvements sortants' }

export default function OngletsStock({ actif }: { actif: string }) {
  return <Onglets items={Object.entries(ONGLETS_STOCK).map(([c, nom]) => ({ nom, href: `/stock/${c}`, actif: c === actif }))} />
}
