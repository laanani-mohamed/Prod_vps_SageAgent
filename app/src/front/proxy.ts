import { NextResponse, type NextRequest } from 'next/server'
import { API_URL, cookiesSession, estHttps, valide } from './lib/session'

// Avant chaque page : sans session → /login ; jeton d'accès expiré (30 min) → renouvelé avec le jeton de rafraîchissement (7 j).
export async function proxy(req: NextRequest) {
  const surLogin = req.nextUrl.pathname === '/login'
  const refresh = req.cookies.get('refresh')?.value
  let access = req.cookies.get('access')?.value
  let renouveles: ReturnType<typeof cookiesSession> | null = null

  if (!valide(access) && valide(refresh)) {
    const r = await fetch(`${API_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    }).catch(() => null)
    if (r?.ok) {
      const j = await r.json()
      access = j.access_token as string
      renouveles = cookiesSession(j.access_token, j.refresh_token, estHttps(req.headers))
      req.cookies.set('access', access) // la page rendue juste après lit déjà le nouveau jeton
    }
  }

  if (!valide(access)) {
    if (surLogin) return NextResponse.next()
    const res = NextResponse.redirect(new URL('/login', req.url))
    res.cookies.delete('access')
    res.cookies.delete('refresh')
    return res
  }

  const res = surLogin ? NextResponse.redirect(new URL('/', req.url)) : NextResponse.next({ request: { headers: req.headers } })
  renouveles?.forEach(([nom, valeur, options]) => res.cookies.set(nom, valeur, options))
  return res
}

export const config = { matcher: ['/((?!_next/|favicon.ico).*)'] }
