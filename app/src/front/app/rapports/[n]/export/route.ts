import { cookies } from 'next/headers'
import { filtresRapport, RAPPORTS } from '../../../../lib/rapports'
import { API_URL, lireJeton } from '../../../../lib/session'

// Téléchargement PDF / Excel d'un rapport : relaie le fichier généré par l'API (jeton de la session).
export async function GET(req: Request, { params }: { params: Promise<{ n: string }> }) {
  const { n } = await params
  const r = RAPPORTS.find((x) => String(x.n) === n)
  const jeton = (await cookies()).get('access')?.value
  if (!r || !jeton) return new Response('Rapport introuvable', { status: 404 })

  const url = new URL(req.url)
  const format = url.searchParams.get('format') === 'xlsx' ? 'xlsx' : 'pdf'
  const { filtres, coNo } = filtresRapport(r.nom, Object.fromEntries(url.searchParams))
  const reponse = await fetch(`${API_URL}/api/bi/rapports/${r.nom}?format=${format}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${jeton}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_schema: lireJeton(jeton).client, filtres, co_no: coNo }),
    cache: 'no-store',
  })
  if (!reponse.ok) return new Response(reponse.status === 403 ? 'Accès refusé' : 'Export impossible', { status: reponse.status })
  return new Response(reponse.body, {
    headers: {
      'Content-Type': reponse.headers.get('content-type') ?? 'application/octet-stream',
      'Content-Disposition': reponse.headers.get('content-disposition') ?? `attachment; filename="${r.nom}.${format}"`,
    },
  })
}
