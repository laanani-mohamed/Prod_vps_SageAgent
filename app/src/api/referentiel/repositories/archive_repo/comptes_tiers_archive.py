"""
bi/referentiel/repositories/archive_repo/comptes_tiers_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveComptesTiersRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_COMPTET", req)

        df_col, _ = require_snapshot(archive_dir, "F_COLLABORATEUR", req)
        if df_col is not None:
            df_col = df_col.select(["co_no", "co_nom", "co_prenom", "co_fonction"])
            df = df.join(df_col, on="co_no", how="left")

        # Filtres
        if req.ct_num:
            df = df.filter(pl.col("ct_num").is_in(req.ct_num))
        if req.ct_intitule:
            df = df.filter(pl.col("ct_intitule").cast(pl.Utf8).str.to_lowercase().str.contains(req.ct_intitule.lower()))
        if req.ct_type:
            df = df.filter(pl.col("ct_type").cast(pl.Int64).is_in(req.ct_type))
        if req.ct_sommeil is not None:
            df = df.filter(pl.col("ct_sommeil").cast(pl.Utf8) == str(req.ct_sommeil))
        if req.ct_identifiant:
            df = df.filter(pl.col("ct_identifiant").cast(pl.Utf8) == req.ct_identifiant)
        if req.ct_ville:
            df = df.filter(pl.col("ct_ville").cast(pl.Utf8).str.to_lowercase().str.contains(req.ct_ville.lower()))
        if req.ct_qualite:
            df = df.filter(pl.col("ct_qualite").cast(pl.Utf8).str.to_lowercase().str.contains(req.ct_qualite.lower()))
        if req.ct_code_region:
            df = df.filter(pl.col("ct_coderegion").cast(pl.Utf8).str.to_lowercase().str.contains(req.ct_code_region.lower()))
        if req.co_no_representant is not None:
            df = df.filter(pl.col("co_no").cast(pl.Int64) == req.co_no_representant)
        
        # Charger les règlements et entêtes de documents pour obtenir les modes de règlement des tiers
        try:
            df_reg = load_archive_file(archive_dir, "F_REGLECH", ts)
            df_ent = load_archive_file(archive_dir, "F_DOCENTETE", ts)
            if df_reg is not None and df_ent is not None:
                df_reg = df_reg.filter(pl.col("do_piece").is_not_null())
                df_ent = df_ent.filter(pl.col("do_piece").is_not_null() & pl.col("do_tiers").is_not_null())
                df_reg_ent = df_reg.join(df_ent.select(["do_piece", "do_tiers"]), on="do_piece", how="inner")
                
                df_modes = df_reg_ent.filter(
                    pl.col("rg_typereg").is_not_null() & (pl.col("rg_typereg") != "")
                ).group_by("do_tiers").agg([
                    pl.col("rg_typereg").mode().first().alias("rg_typereg")
                ])
                
                PAYMENT_MODES = {
                    "0": "Virement",
                    "1": "Chèque",
                    "2": "Traite",
                    "3": "Espèces",
                    "4": "Carte Bancaire"
                }
                
                modes_dict = {
                    r["do_tiers"]: PAYMENT_MODES.get(str(r["rg_typereg"]), "Virement")
                    for r in df_modes.to_dicts()
                    if r["do_tiers"] is not None
                }
            else:
                modes_dict = {}
        except Exception:
            modes_dict = {}

        df = df.sort("ct_intitule")
        data = df.to_dicts()

        # Enrichir chaque tiers avec ICE, IF et Mode de Règlement
        import re
        for row in data:
            ct_num = row.get("ct_num")
            
            # 1. Mode de règlement
            row["mode_reglement"] = modes_dict.get(ct_num, "Virement")
            
            # 2. Extraction de l'ICE et Identifiant Fiscal (IF)
            ice = "-"
            if_fiscal = "-"
            
            candidate_fields = ["ct_coderegion", "ct_identifiant", "ct_qualite", "ct_complement", "ct_adresse"]
            
            # Recherche de l'ICE
            for field in candidate_fields:
                val = str(row.get(field) or "").strip()
                if not val or val.lower() in ("nan", "none", "null", "-"):
                    continue
                if "ice" in val.lower():
                    cleaned = "".join([c for c in val if c.isdigit()])
                    if cleaned:
                        ice = cleaned
                        break
                match = re.search(r'\b\d{15}\b', val)
                if match:
                    ice = match.group(0)
                    break
                    
            # Recherche de l'IF
            for field in candidate_fields:
                val = str(row.get(field) or "").strip()
                if not val or val.lower() in ("nan", "none", "null", "-"):
                    continue
                if "if" in val.lower() and not "tarif" in val.lower() and not "actif" in val.lower():
                    cleaned = val.replace("IF", "").replace("if", "").strip()
                    cleaned = "".join([c for c in cleaned if c.isalnum()])
                    if cleaned:
                        if_fiscal = cleaned
                        break
                match = re.search(r'\b\d{7,10}\b', val)
                if match:
                    candidate_if = match.group(0)
                    if candidate_if != ice:
                        if_fiscal = candidate_if
                        break
                        
            # Fallbacks
            ident = str(row.get("ct_identifiant") or "").strip()
            if ident and ident.lower() not in ("nan", "none", "null", "-"):
                digits_ident = "".join([c for c in ident if c.isdigit()])
                if len(digits_ident) == 15:
                    ice = digits_ident
                elif ice == "-":
                    ice = ident
                elif if_fiscal == "-" and digits_ident != ice and "ice" not in ident.lower():
                    if_fiscal = ident
                    
            qual = str(row.get("ct_qualite") or "").strip()
            if qual and "if" in qual.lower() and if_fiscal == "-":
                if_fiscal = qual.replace("IF", "").replace("if", "").strip()
                
            row["ice"] = ice
            row["if_fiscal"] = if_fiscal

        if data:
            data[0]["__source_timestamp__"] = ts
        return data
