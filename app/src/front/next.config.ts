import type { NextConfig } from 'next'

// Entrée d'une section → son premier onglet
const config: NextConfig = {
  async redirects() {
    return [
      { source: '/fichier-de-base', destination: '/fichier-de-base/articles', permanent: false },
      { source: '/stock', destination: '/stock/etat', permanent: false },
      { source: '/reglements', destination: '/reglements/encaissements', permanent: false },
      { source: '/rapports', destination: '/rapports/1', permanent: false },
    ]
  },
}

export default config
