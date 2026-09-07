from .base import call_api, call_api_get, check_api_health, APIClient
from .bi_service import get_dashboard_kpis, get_dashboard_objectifs, get_dashboard_analytique, get_rapport_ca, get_top_clients
from .documents_service import get_documents_entete, get_documents_ligne, get_formatted_documents
from .referentiel_service import get_articles, get_comptes_tiers, get_depots, get_familles, get_lots_series, get_collaborateurs
from .reglements_service import get_reglements_data, get_formatted_reglements
from .stock_service import get_stock_availability, get_stock_insights, get_mouvements_entrants, get_mouvements_sortants
from .article_service import get_article_top_clients, get_article_stock_depots, get_article_stats
from .sales_service import get_sales_documents, Ventes, Achats, Chiffre_affaire_net, get_monthly_sales_and_profit, Valeur_stock, Encours_clients, Clients_actifs
from .top_client_service import get_top_clients_from_docentete
from .tiers_service import search_comptes_tiers
from .depot_service import get_depots_summary

__all__ = [
    "call_api", "call_api_get", "check_api_health", "APIClient",
    "get_dashboard_kpis", "get_dashboard_objectifs", "get_dashboard_analytique", "get_rapport_ca", "get_top_clients",
    "get_documents_entete", "get_documents_ligne", "get_formatted_documents",
    "get_articles", "get_comptes_tiers", "get_depots", "get_familles", "get_lots_series", "get_collaborateurs",
    "get_reglements_data", "get_formatted_reglements",
    "get_stock_availability", "get_stock_insights", "get_mouvements_entrants", "get_mouvements_sortants",
    "get_article_top_clients", "get_article_stock_depots", "get_article_stats",
    "get_sales_documents", "Ventes", "Achats", "Chiffre_affaire_net", "get_monthly_sales_and_profit", "Valeur_stock", "Encours_clients", "Clients_actifs",
    "get_top_clients_from_docentete",
    "search_comptes_tiers",
    "get_depots_summary"
]
