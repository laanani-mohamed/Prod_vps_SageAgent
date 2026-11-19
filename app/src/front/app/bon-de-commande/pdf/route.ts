import { cookies } from 'next/headers'
import { API_URL, lireJeton } from '../../../lib/session'

// PDF du bon de commande : relaie la saisie à l'API (jeton de la session ; client Sage = celui du jeton).
export async function POST(req: Request) {
  const jeton = (await cookies()).get('access')?.value
  if (!jeton) return new Response('Session expirée', { status: 401 })
  const saisie = await req.json().catch(() => null)
  if (!saisie) return new Response('Requête invalide', { status: 400 })

  const reponse = await fetch(`${API_URL}/api/bi/bon-commande`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${jeton}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_schema: lireJeton(jeton).client, ct_num: saisie.ct_num, lignes: saisie.lignes, remise_globale: saisie.remise_globale,
    }),
    cache: 'no-store',
  })
  if (!reponse.ok) return new Response('Génération impossible', { status: reponse.status })
  return new Response(reponse.body, {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': reponse.headers.get('content-disposition') ?? 'attachment; filename="bon_de_commande.pdf"',
    },
  })
}
