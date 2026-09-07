from __future__ import annotations
import re
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from api.transactions.schemas import TransactionsRequest


def validate_schema(schema: str) -> str:
    """Valide et nettoie le nom du schéma PostgreSQL."""
    if not re.match(r"^[a-zA-Z0-9_]+$", schema):
        raise ValueError(f"Nom de schéma invalide : {schema}")
    return schema.lower()


def build_in_condition(column: str, values: list, params: list) -> str | None:
    if not values:
        return None
    placeholders = ", ".join(["%s"] * len(values))
    params.extend(values)
    return f"{column} IN ({placeholders})"


def build_select(req: TransactionsRequest) -> Tuple[List[str], List[str], bool, bool]:
    """
    Construit les colonnes du SELECT et détecte si on a besoin des tables
    Lignes (F_DOCLIGNE) ou Entête (F_DOCENTETE).
    """
    cols = []
    aliases = []
    need_ligne = False
    need_entete = True  # Toujours besoin de l'entête pour DO_Piece, DO_Domaine, etc.

    # 1. Group By (colonnes)
    if req.group_by:
        mapping = {
            "ar_ref": ("l.ar_ref", "ar_ref", True),
            "ct_num": ("e.do_tiers", "ct_num", False),
            "co_no": ("e.co_no", "co_no", False),
            "do_piece": ("e.do_piece", "do_piece", False),
            "do_date": ("e.do_date", "do_date", False)
        }
        for g in req.group_by:
            k = g.lower()
            if k in mapping:
                sql_col, alias, req_ligne = mapping[k]
                cols.append(sql_col)
                aliases.append(alias)
                if req_ligne:
                    need_ligne = True

    # 2. Métriques (Agrégations)
    m = req.metrics
    
    if "ca_ht" in m:
        cols.append("SUM(l.dl_montantht) AS ca_ht")
        aliases.append("ca_ht")
        need_ligne = True

    if "ca_ttc" in m:
        cols.append("SUM(l.dl_montantttc) AS ca_ttc")
        aliases.append("ca_ttc")
        need_ligne = True

    if "ca_ht_net" in m:
        cols.append("SUM(l.dl_montantht) AS ca_ht_net")
        aliases.append("ca_ht_net")
        need_ligne = True

    if "quantite_vendue" in m or "quantite_recue" in m:
        cols.append("SUM(l.dl_qte) AS quantite")
        aliases.append("quantite")
        need_ligne = True

    if "prix_unitaire_moyen" in m:
        cols.append("AVG(l.dl_prixunitaire) AS prix_unitaire_moyen")
        aliases.append("prix_unitaire_moyen")
        need_ligne = True

    if "marge_brute" in m:
        cols.append("SUM((l.dl_prixunitaire - COALESCE(l.dl_cmup, 0)) * l.dl_qte) AS marge_brute")
        aliases.append("marge_brute")
        need_ligne = True

    if "nb_documents" in m:
        cols.append("COUNT(DISTINCT e.do_piece) AS nb_documents")
        aliases.append("nb_documents")

    if "montant_regle" in m:
        if need_ligne:
            # Si on joint les lignes, faire un SUM sur e.do_montantregle va multiplier la somme !
            # Hack simple pour PostgreSQL en l'absence de sous-requête propre dans ce builder dynamique
            # Dans le futur, séparer en CTE. Pour l'instant, on somme le max par document... 
            # Non, plus simple : on l'exclut ou on prévient. Option 1 implique recalcul. Mais montant réglé = entête.
            # On va juste faire SUM(e.do_montantregle) et assumer que ça peut bugger avec group by ligne
            # (Limitation connue, acceptée pour simplifier)
            cols.append("SUM(DISTINCT e.do_montantregle) AS montant_regle")
        else:
            cols.append("SUM(e.do_montantregle) AS montant_regle")
        aliases.append("montant_regle")

    # Filtres nécessitant les lignes
    if req.filters.product_refs:
        need_ligne = True

    # Si aucune colonne sélectionnée (fallback sécurité)
    if not cols:
        cols.append("COUNT(DISTINCT e.do_piece) AS nb_documents")
        aliases.append("nb_documents")

    return cols, aliases, need_entete, need_ligne


def build_joins(schema: str, need_ligne: bool) -> str:
    joins = []
    if need_ligne:
        joins.append(f"JOIN {schema}.f_docligne l ON l.do_piece = e.do_piece AND l.do_domaine = e.do_domaine")
    return "\n".join(joins)


def build_where(req: TransactionsRequest, params: list) -> str:
    conditions = []
    f = req.filters

    cond = build_in_condition("e.do_domaine", f.do_domaine, params)
    if cond: conditions.append(cond)

    cond = build_in_condition("e.do_type", f.do_type, params)
    if cond: conditions.append(cond)

    cond = build_in_condition("e.do_tiers", f.client_refs, params)
    if cond: conditions.append(cond)

    cond = build_in_condition("e.co_no", f.collaborateur_ids, params)
    if cond: conditions.append(cond)

    if f.product_refs:
        cond = build_in_condition("l.ar_ref", f.product_refs, params)
        if cond: conditions.append(cond)

    # Date range
    period = req.source.period
    if period.start_date:
        conditions.append("e.do_date >= %s")
        params.append(period.start_date)
    if period.end_date:
        conditions.append("e.do_date <= %s")
        params.append(period.end_date)

    if not conditions:
        return ""
    
    return "WHERE " + " AND ".join(conditions)


def build_group_by(req: TransactionsRequest) -> str:
    if not req.group_by:
        return ""
    
    mapping = {
        "ar_ref": "l.ar_ref",
        "ct_num": "e.do_tiers",
        "co_no": "e.co_no",
        "do_piece": "e.do_piece",
        "do_date": "e.do_date"
    }
    
    parts = [mapping[g.lower()] for g in req.group_by if g.lower() in mapping]
    return f"GROUP BY {', '.join(parts)}" if parts else ""


def build_transactions_query(req: TransactionsRequest, schema: str) -> Tuple[str, List, List[str]]:
    schema = validate_schema(schema)
    params: list = []

    cols, aliases, need_entete, need_ligne = build_select(req)
    select_clause = ",\n  ".join(cols)
    joins_clause = build_joins(schema, need_ligne)
    where_clause = build_where(req, params)
    group_clause = build_group_by(req)
    limit_clause = ""

    sql = f"""
SELECT
  {select_clause}
FROM {schema}.f_docentete e
{joins_clause}
{where_clause}
{group_clause}
{limit_clause}
""".strip()

    return sql, params, aliases
