import { cookies } from 'next/headers'
import { lireJeton } from '../lib/session'
import { deconnexion } from './actions'

// Accueil provisoire : les pages du tableau de bord prendront sa place.
export default async function Accueil() {
  const s = lireJeton((await cookies()).get('access')!.value) // présent et valide : vérifié par proxy.ts
  return (
    <main className="accueil">
      <div className="carte">
        <h1>Bienvenue, {s.username}</h1>
        <p className="aide">
          Profil {s.roles.join(', ')} · client {s.client}
          {s.coNo ? ` · collaborateur n° ${s.coNo}` : ''}
        </p>
        <form action={deconnexion}>
          <button type="submit" className="principal">Se déconnecter</button>
        </form>
      </div>
    </main>
  )
}
