"""
api/bi/repositories/pg_repo/bi_stats_tiers_repo.py

Repository PostgreSQL des statistiques d'un tiers (POST /api/bi/stats-tiers).
Une méthode par jeu de données brut ; les calculs sont faits dans
business_logic/stats_tiers_calculations.py.

Règles appliquées :
  - jointure ligne → entête sur (do_domaine, do_type, do_piece)
  - commercial = F_DOCENTETE.co_no (0 → "Non identifié")
  - dates comparées sur la partie date seule (do_date est un timestamp)
"""
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema

# Types de documents Sage utilisés
TYPES_FACTURE = {0: [6, 7], 1: [16, 17]}
TYPE_DEVIS_VENTE = 0
TYPE_BL_ACHAT = 13
TYPE_RETOUR_ACHAT = 14

_DATE = "LEFT(CAST({col} AS TEXT), 10)"


def _in(values: List[int]) -> str:
    return ", ".join(str(int(v)) for v in values)


class PgBIStatsTiersRepository(BaseBIRepository):

    def fetch(self, req) -> List[Dict[str, Any]]:
        raise NotImplementedError("Utiliser les méthodes fetch_* spécialisées")

    def _run(self, builder, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(builder, req, schema)
        return data

    # ── Entêtes du tiers (factures, avoirs, devis, retours) sur [date_from, date_to] ──
    def fetch_entetes(self, req, types: List[int], date_from: str, date_to: str) -> List[Dict[str, Any]]:
        q = SimpleNamespace(client_schema=req.client_schema, ct_num=req.ct_num, ct_type=req.ct_type,
                            types=types, date_from=date_from, date_to=date_to)
        return self._run(self._q_entetes, q)

    def _q_entetes(self, q, schema: str) -> Tuple[str, list, list]:
        d = _DATE.format(col="e.do_date")
        sql = f"""
SELECT e.do_type, {d} AS do_date, e.do_piece,
       COALESCE(e.do_totalht, 0) AS do_totalht,
       COALESCE(e.co_no, 0) AS co_no,
       CASE
           WHEN COALESCE(e.co_no, 0) = 0 THEN 'Non identifié'
           ELSE COALESCE(
               NULLIF(CONCAT_WS(' ', NULLIF(TRIM(col.co_nom), ''), NULLIF(TRIM(col.co_prenom), '')), ''),
               'Commercial ' || e.co_no
           )
       END AS co_fullname
FROM {schema}.f_docentete e
LEFT JOIN {schema}.f_collaborateur col ON col.co_no = e.co_no
WHERE e.do_domaine = %s AND e.do_tiers = %s AND e.do_type IN ({_in(q.types)})
  AND {d} >= %s AND {d} <= %s""".strip()
        cols = ["do_type", "do_date", "do_piece", "do_totalht", "co_no", "co_fullname"]
        return sql, [q.ct_type, q.ct_num, q.date_from, q.date_to], cols

    # ── Encours / dettes (tout l'historique) et date de la dernière facture ──
    def fetch_solde(self, req) -> Dict[str, Any]:
        rows = self._run(self._q_solde, req)
        return rows[0] if rows else {"solde": 0, "derniere_facture": None}

    def _q_solde(self, req, schema: str) -> Tuple[str, list, list]:
        reste = "COALESCE(e.do_totalttc, 0) - COALESCE(e.do_montantregle, 0)"
        sql = f"""
SELECT COALESCE(SUM({reste}) FILTER (WHERE ROUND(CAST({reste} AS NUMERIC), 2) > 0), 0) AS solde,
       MAX({_DATE.format(col="e.do_date")}) AS derniere_facture
FROM {schema}.f_docentete e
WHERE e.do_domaine = %s AND e.do_tiers = %s AND e.do_type IN ({_in(TYPES_FACTURE[req.ct_type])})""".strip()
        return sql, [req.ct_type, req.ct_num], ["solde", "derniere_facture"]

    # ── Lignes du tiers sur la période (factures ; + BL côté achat pour les délais) ──
    def fetch_lignes(self, req, types: List[int]) -> List[Dict[str, Any]]:
        q = SimpleNamespace(client_schema=req.client_schema, ct_num=req.ct_num, ct_type=req.ct_type,
                            types=types, date_from=req.date_from, date_to=req.date_to)
        return self._run(self._q_lignes, q)

    def _q_lignes(self, q, schema: str) -> Tuple[str, list, list]:
        d = _DATE.format(col="e.do_date")
        sql = f"""
SELECT l.do_domaine, l.do_type, {d} AS do_date,
       l.ar_ref, COALESCE(NULLIF(TRIM(a.ar_design), ''), l.dl_design, l.ar_ref) AS designation,
       COALESCE(NULLIF(TRIM(f.fa_intitule), ''), 'Sans famille') AS famille,
       l.dl_qte, l.dl_qtebl, l.dl_montantht, l.dl_prixunitaire, l.dl_prixru, l.dl_cmup, a.ar_prixach,
       {_DATE.format(col="l.dl_datebc")} AS dl_datebc, {_DATE.format(col="l.dl_datebl")} AS dl_datebl
FROM {schema}.f_docligne l
JOIN {schema}.f_docentete e ON e.do_domaine = l.do_domaine AND e.do_type = l.do_type AND e.do_piece = l.do_piece
LEFT JOIN {schema}.f_article a ON a.ar_ref = l.ar_ref
LEFT JOIN {schema}.f_famille f ON f.fa_codefamille = a.fa_codefamille
WHERE e.do_domaine = %s AND e.do_tiers = %s AND e.do_type IN ({_in(q.types)})
  AND {d} >= %s AND {d} <= %s""".strip()
        cols = ["do_domaine", "do_type", "do_date", "ar_ref", "designation", "famille",
                "dl_qte", "dl_qtebl", "dl_montantht", "dl_prixunitaire", "dl_prixru", "dl_cmup", "ar_prixach",
                "dl_datebc", "dl_datebl"]
        return sql, [q.ct_type, q.ct_num, q.date_from, q.date_to], cols

    # ── Achats HT de tous les fournisseurs sur la période (part, rang, concentration) ──
    def fetch_achats_par_fournisseur(self, req) -> List[Dict[str, Any]]:
        return self._run(self._q_achats_fournisseurs, req)

    def _q_achats_fournisseurs(self, req, schema: str) -> Tuple[str, list, list]:
        d = _DATE.format(col="e.do_date")
        sql = f"""
SELECT e.do_tiers, SUM(COALESCE(e.do_totalht, 0)) AS achats_ht
FROM {schema}.f_docentete e
WHERE e.do_domaine = 1 AND e.do_type IN ({_in(TYPES_FACTURE[1])}) AND {d} >= %s AND {d} <= %s
GROUP BY e.do_tiers""".strip()
        return sql, [req.date_from, req.date_to], ["do_tiers", "achats_ht"]

    # ── Prix d'achat moyens de tous les fournisseurs pour des articles donnés (comparaison) ──
    def fetch_prix_fournisseurs(self, req, ar_refs: List[str]) -> List[Dict[str, Any]]:
        if not ar_refs:
            return []
        q = SimpleNamespace(client_schema=req.client_schema, ar_refs=ar_refs,
                            date_from=req.date_from, date_to=req.date_to)
        return self._run(self._q_prix_fournisseurs, q)

    def _q_prix_fournisseurs(self, q, schema: str) -> Tuple[str, list, list]:
        d = _DATE.format(col="e.do_date")
        sql = f"""
SELECT l.ar_ref, e.do_tiers, COALESCE(NULLIF(TRIM(ct.ct_intitule), ''), e.do_tiers) AS fournisseur,
       SUM(l.dl_montantht) / NULLIF(SUM(l.dl_qte), 0) AS prix_moyen
FROM {schema}.f_docligne l
JOIN {schema}.f_docentete e ON e.do_domaine = l.do_domaine AND e.do_type = l.do_type AND e.do_piece = l.do_piece
LEFT JOIN {schema}.f_comptet ct ON ct.ct_num = e.do_tiers
WHERE e.do_domaine = 1 AND e.do_type IN ({_in(TYPES_FACTURE[1])})
  AND l.dl_qte > 0 AND l.dl_prixunitaire > 0 AND l.ar_ref = ANY(%s)
  AND {d} >= %s AND {d} <= %s
GROUP BY l.ar_ref, e.do_tiers, ct.ct_intitule""".strip()
        return sql, [list(q.ar_refs), q.date_from, q.date_to], ["ar_ref", "do_tiers", "fournisseur", "prix_moyen"]
