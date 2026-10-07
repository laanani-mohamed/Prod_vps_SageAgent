"""
rapports_config.py
Rapports à générer pour chaque client (src/reporting/generate.py, future tâche planifiée).

Clé    = clé client de data_Client/reference/auth.json (ex : "CROSS").
Valeur = {"destinataires": [...], "rapports": [...]}
  "destinataires"  adresse(s) email du client, ex : ["compta@client.ma", "directeur@client.ma"].
                   Chaque adresse reçoit UN email avec tous les rapports du client (PDF + Excel),
                   envoyé depuis le compte Gmail de app/.env.mail. Vide ou absent = rapports
                   déposés dans storage_srv/rapport/ sans envoi.
  "rapports"       liste de {"rapport": <nom>, "filtres": {...}}. "filtres" est facultatif : un filtre
                   absent prend la valeur par défaut indiquée ci-dessous (celle de l'écran Rapports).
Un même rapport peut apparaître plusieurs fois avec des filtres différents : les fichiers du jour
sont alors nommés <nom>.pdf, <nom>_2.pdf, ... et le .json associé indique les filtres de chacun
(et le résultat des envois, clé "envois").

Rapports et filtres disponibles
--------------------------------
chiffre_affaire    group_by    "client" | "region" | "commercial"                     (défaut "client")
                   periode     voir PÉRIODES ci-dessous                                 (défaut "annee_en_cours")
                   date_from / date_to   "AAAA-MM-JJ" — dates fixes, remplacent periode

comparaison_ca     group_by    idem chiffre_affaire
                   periode     période 2 (comparée) ; la période 1 (référence) est la même
                               période un an plus tôt                                  (défaut "annee_en_cours")
                   date_from_1 / date_to_1 / date_from_2 / date_to_2   dates fixes, remplacent periode

balance            commercial  code collaborateur (co_no), 0 = Non identifié          (défaut : tous)
balance_agee       commercial  idem

valeur_stock       depots      liste d'intitulés de dépôt, ex : ["SIEGE", "MAGAZIN"]   (défaut : tous)
                   familles    liste d'intitulés de famille                            (défaut : toutes)
                   articles    liste de désignations d'article                         (défaut : tous)

visite_client      client      code client Sage (ct_num), ex : "C0015" — OBLIGATOIRE
                               (un rapport par client Sage : répéter l'entrée pour chacun)

produits_dormants  mois        mois sans vente                                         (défaut 6)
lots_peremption    jours       jours avant péremption                                  (défaut 60)
consommation       aucun filtre (6 derniers mois)

PÉRIODES (calculées le jour de la génération)
    "annee_en_cours"     1er janvier → aujourd'hui
    "mois_en_cours"      1er du mois → aujourd'hui
    "mois_precedent"     mois précédent complet
    "annee_precedente"   année précédente complète
"""
    # Exemple avec tous les rapports (à copier sous la clé d'un client) :
    # "CLIENT": {
    #     "destinataires": ["compta@client.ma", "directeur@client.ma"],
    #     "rapports": [
    #         {"rapport": "chiffre_affaire",   "filtres": {"group_by": "region", "periode": "mois_precedent"}},
    #         {"rapport": "comparaison_ca",    "filtres": {"group_by": "commercial", "periode": "annee_en_cours"}},
    #         {"rapport": "balance",           "filtres": {"commercial": 5}},
    #         {"rapport": "balance_agee"},
    #         {"rapport": "valeur_stock",      "filtres": {"depots": ["SIEGE"], "familles": ["ACDELCO", "AJUSA"]}},
    #         {"rapport": "visite_client",     "filtres": {"client": "C0015"}},
    #         {"rapport": "produits_dormants", "filtres": {"mois": 12}},
    #         {"rapport": "lots_peremption",   "filtres": {"jours": 120}},
    #         {"rapport": "consommation"},
    #     ],
    # },

RAPPORTS_CLIENTS = {
    "CROSS": {
        "destinataires": ["mlaanani@datateam.ma","merouan24@gmail.com"],
        "rapports": [
            {"rapport": "chiffre_affaire", "filtres": {"group_by": "client", "periode": "annee_en_cours"}},
            {"rapport": "chiffre_affaire", "filtres": {"group_by": "region", "periode": "mois_precedent"}},
            {"rapport": "lots_peremption", "filtres": {"jours": 120}},
        ],
    },

    "health": {
        "destinataires": ["mlaanani@datateam.ma","merouan24@gmail.com"],
        "rapports": [
            {"rapport": "chiffre_affaire",   "filtres": {"group_by": "region", "periode": "mois_precedent"}},
            {"rapport": "comparaison_ca",    "filtres": {"group_by": "commercial", "periode": "annee_en_cours"}},
            {"rapport": "balance",           "filtres": {"commercial": 2}},
            {"rapport": "visite_client",     "filtres": {"client": "CLT004"}},
        ],
    },
}


