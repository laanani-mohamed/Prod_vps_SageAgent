"""
api/bi/repositories/pg_repo/bi_visite_client_repo.py

Repository PostgreSQL pour le Rapport Client Avant Visite.
Retourne les 7 jeux de données bruts filtrés sur un do_tiers spécifique.
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema


class PgBIVisiteClientRepository(BaseBIRepository):
    """
    Repository pour le Rapport Client Avant Visite.
    Expose plusieurs méthodes fetch_* spécialisées plutôt qu'un fetch() générique.
    """

    def fetch(self, req):
        # Méthode générique non utilisée — ce repo expose des fetch_* spécialisés
        raise NotImplementedError("Utiliser fetch_bc_en_cours, fetch_factures_impayees, etc.")



    # ── 1. Bons de commande en cours (do_type=1) ─────────────────────────────
    def fetch_bc_en_cours(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._query_bc_en_cours, req, schema)
        return data

    def _query_bc_en_cours(self, req, schema: str) -> Tuple[str, list, list]:
        col_aliases = ["do_piece", "do_date", "do_totalht", "do_totalttc"]
        sql = f"""
SELECT
    e.do_piece,
    CAST(e.do_date AS TEXT) AS do_date,
    COALESCE(e.do_totalht,  0) AS do_totalht,
    COALESCE(e.do_totalttc, 0) AS do_totalttc
FROM {schema}.f_docentete e
WHERE e.do_domaine = 0
  AND e.do_type = 1
  AND e.do_tiers = %s
ORDER BY e.do_date DESC
""".strip()
        return sql, [req.do_tiers], col_aliases

    # ── 2. Factures non réglées (do_type IN (6,7), reste > 0) ───────────────
    def fetch_factures_impayees(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._query_factures_impayees, req, schema)
        return data

    def _query_factures_impayees(self, req, schema: str) -> Tuple[str, list, list]:
        col_aliases = ["do_piece", "do_date", "do_totalht", "do_totalttc", "reste_a_payer"]
        sql = f"""
SELECT
    e.do_piece,
    CAST(e.do_date AS TEXT) AS do_date,
    COALESCE(e.do_totalht,  0) AS do_totalht,
    COALESCE(e.do_totalttc, 0) AS do_totalttc,
    COALESCE(e.do_totalttc, 0) - COALESCE(e.do_montantregle, 0) AS reste_a_payer
FROM {schema}.f_docentete e
WHERE e.do_domaine = 0
  AND e.do_type IN (6, 7)
  AND e.do_tiers = %s
  AND ROUND(CAST(COALESCE(e.do_totalttc, 0) - COALESCE(e.do_montantregle, 0) AS NUMERIC), 2) > 0
ORDER BY e.do_date DESC
""".strip()
        return sql, [req.do_tiers], col_aliases

    # ── 3. Lignes de vente (do_type=6) pour pivot articles/mois ─────────────
    def fetch_lignes_vente(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._query_lignes_vente, req, schema)
        return data

    def _query_lignes_vente(self, req, schema: str) -> Tuple[str, list, list]:
        col_aliases = ["ar_ref", "dl_design", "do_date", "dl_qte", "dl_montantht", "do_type"]
        sql = f"""
SELECT
    COALESCE(l.ar_ref,    '')  AS ar_ref,
    COALESCE(l.dl_design, '')  AS dl_design,
    CAST(e.do_date AS TEXT)    AS do_date,
    COALESCE(l.dl_qte,       0)   AS dl_qte,
    COALESCE(l.dl_montantht, 0)   AS dl_montantht,
    e.do_type
FROM {schema}.f_docligne l
JOIN {schema}.f_docentete e ON e.do_piece = l.do_piece
WHERE e.do_domaine = 0
  AND e.do_type IN (6, 7)
  AND e.do_tiers = %s
  AND CAST(e.do_date AS TEXT) >= %s
ORDER BY ar_ref, do_date
""".strip()
        return sql, [req.do_tiers, req.date_from], col_aliases

    # ── 4. Familles vendues au client (tous temps) ──────────────────────────
    def fetch_familles_vendues(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._query_familles_vendues, req, schema)
        return data

    def _query_familles_vendues(self, req, schema: str) -> Tuple[str, list, list]:
        col_aliases = ["fa_codefamille", "fa_intitule", "ca_ht", "last_date"]
        sql = f"""
SELECT
    COALESCE(a.fa_codefamille, '__SANS__') AS fa_codefamille,
    COALESCE(f.fa_intitule,    'Sans famille') AS fa_intitule,
    COALESCE(SUM(COALESCE(l.dl_montantht, 0)), 0) AS ca_ht,
    MAX(CAST(e.do_date AS TEXT)) AS last_date
FROM {schema}.f_docligne l
JOIN {schema}.f_docentete e ON e.do_piece = l.do_piece
LEFT JOIN {schema}.f_article  a ON a.ar_ref = l.ar_ref
LEFT JOIN {schema}.f_famille  f ON f.fa_codefamille = a.fa_codefamille
WHERE e.do_domaine = 0
  AND e.do_type IN (6, 7)
  AND e.do_tiers = %s
GROUP BY a.fa_codefamille, f.fa_intitule
ORDER BY ca_ht DESC
""".strip()
        return sql, [req.do_tiers], col_aliases

    # ── 5. Toutes les familles du référentiel ────────────────────────────────
    def fetch_toutes_familles(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._query_toutes_familles, req, schema)
        return data

    def _query_toutes_familles(self, req, schema: str) -> Tuple[str, list, list]:
        col_aliases = ["fa_codefamille", "fa_intitule"]
        sql = f"""
SELECT fa_codefamille, COALESCE(fa_intitule, '') AS fa_intitule
FROM {schema}.f_famille
ORDER BY fa_codefamille
""".strip()
        return sql, [], col_aliases
