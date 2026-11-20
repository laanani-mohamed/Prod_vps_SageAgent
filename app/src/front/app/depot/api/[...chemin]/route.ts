import { cookies } from 'next/headers'
import { API_URL, lireJeton } from '../../../../lib/session'

// Relais de la page « Dépôt des fichiers » vers /api/depot/* (api/depot/router.py), avec le jeton de la session
// et le client Sage du jeton. Le corps passe en flux : un fichier de plus de 170 Mo n'est jamais gardé en mémoire
// (les envois de fichiers sont exclus de proxy.ts, qui sinon le garderait en mémoire et le couperait à 10 Mo).
async function relayer(req: Request, { params }: { params: Promise<{ chemin: string[] }> }) {
  const jeton = (await cookies()).get('access')?.value
  if (!jeton) return new Response('Session expirée', { status: 401 })
  const q = new URL(req.url).searchParams
  q.set('client_schema', lireJeton(jeton).client ?? '')
  const r = await fetch(`${API_URL}/api/depot/${(await params).chemin.map(encodeURIComponent).join('/')}?${q}`, {
    method: req.method,
    headers: { Authorization: `Bearer ${jeton}` },
    body: req.body,
    duplex: 'half',
    cache: 'no-store',
  } as RequestInit)
  const entetes = new Headers({ 'Content-Type': r.headers.get('content-type') ?? 'application/json' })
  const fichier = r.headers.get('content-disposition')
  if (fichier) entetes.set('Content-Disposition', fichier)
  return new Response(r.body, { status: r.status, headers: entetes })
}

export { relayer as GET, relayer as PUT, relayer as POST, relayer as DELETE }
