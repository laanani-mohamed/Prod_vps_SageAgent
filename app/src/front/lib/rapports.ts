import { lire, type Params } from './params'

// Les 9 rapports (POST /api/bi/rapports/{nom}) : couleur propre à chacun ; `stock` = réservé au directeur.
export const RAPPORTS = [
  { n: 1, nom: 'chiffre_affaire', titre: "Chiffre d'Affaire", menu: "Chiffre d'Affaire", couleur: '#00a5cf' },
  { n: 2, nom: 'comparaison_ca', titre: "Comparaison Chiffre d'Affaire", menu: 'Comparaison CA', couleur: '#25a18e' },
  { n: 3, nom: 'balance', titre: 'Balance par Clients', menu: 'Balance par Clients', couleur: '#f35b04' },
  { n: 4, nom: 'valeur_stock', titre: 'Valeur du Stock', menu: 'Valeur du Stock', couleur: '#f7b801', stock: true },
  { n: 5, nom: 'visite_client', titre: 'Avant Visite Client', menu: 'Avant Visite Client', couleur: '#bcc72f' },
  { n: 6, nom: 'produits_dormants', titre: 'Produits Dormants', menu: 'Produits Dormants', couleur: '#fe6d73', stock: true },
  { n: 7, nom: 'lots_peremption', titre: 'Lots en Péremption', menu: 'Lots en Péremption', couleur: '#266967', stock: true },
  { n: 8, nom: 'consommation', titre: 'Consommation des Articles par Produits', menu: 'Consommation', couleur: '#7678ed', stock: true },
  { n: 9, nom: 'balance_agee', titre: 'Balance Âgée par Clients', menu: 'Balance Âgée', couleur: '#467599' },
] as const

export type Rapport = (typeof RAPPORTS)[number]

// Paramètres d'URL → filtres de l'API (mêmes clés que config/rapports_config.py)
const CLES: Record<string, string[]> = {
  chiffre_affaire: ['group_by', 'date_from', 'date_to'],
  comparaison_ca: ['group_by', 'date_from_1', 'date_to_1', 'date_from_2', 'date_to_2'],
  visite_client: ['client'],
  produits_dormants: ['mois'],
  lots_peremption: ['jours'],
}
const LISTES: Record<string, string> = { depot: 'depots', famille: 'familles', article: 'articles' }

/** Filtres et commercial (co_no, directeur) du rapport `nom` lus dans l'URL. */
export function filtresRapport(nom: string, p: Params) {
  const filtres: Record<string, unknown> = {}
  for (const cle of CLES[nom] ?? []) {
    const v = lire(p, cle)
    if (v) filtres[cle] = cle === 'mois' || cle === 'jours' ? Number(v) : v
  }
  if (nom === 'valeur_stock') {
    for (const [cle, filtre] of Object.entries(LISTES)) if (lire(p, cle)) filtres[filtre] = [lire(p, cle)]
  }
  const commercial = lire(p, 'commercial')
  return { filtres, coNo: commercial ? [Number(commercial)] : [] }
}
