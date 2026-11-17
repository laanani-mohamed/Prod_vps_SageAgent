import Documents from '../../components/Documents'
import type { Params } from '../../lib/params'

export default async function PageAchats({ searchParams }: { searchParams: Promise<Params> }) {
  return <Documents domaine={1} p={await searchParams} chemin="/achats" />
}
