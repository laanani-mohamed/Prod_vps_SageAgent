'use client'

// Erreur pendant le chargement d'une page (API injoignable ou en erreur).
export default function Erreur({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="connexion"><main className="formulaire">
      <div className="carte" role="alert">
        <h1>Les données n&apos;ont pas pu être chargées</h1>
        <p className="aide">Le serveur API n&apos;a pas répondu correctement. Réessayez dans un instant.</p>
        <button type="button" className="principal" onClick={reset}>Réessayer</button>
      </div>
    </main></div>
  )
}
