import Documents from '../../components/Documents'
import type { Params } from '../../lib/params'

export default async function PageVentes({ searchParams }: { searchParams: Promise<Params> }) {
  return <Documents domaine={0} p={await searchParams} chemin="/ventes" />
}
