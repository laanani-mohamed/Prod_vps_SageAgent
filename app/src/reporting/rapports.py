"""
reporting/rapports.py — Mise en forme des rapports : lignes renvoyées par l'API → DataFrame(s) + titres.

Sans Streamlit ni accès base. Reprend la logique des onglets de dashboard_bi/pages/7_Rapports.py
pour que le rapport généré par la tâche planifiée soit identique à celui téléchargé depuis le dashboard.
"""
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

logger = logging.getLogger("reporting.rapports")


@dataclass
class Rapport:
    nom: str                        # nom des fichiers déposés : <nom>.pdf / <nom>.xlsx / <nom>.json
    titre: str
    sous_titre: str
    sections: list                  # [(libellé, DataFrame)] — une seule pour la plupart des rapports
    pdf_par_section: bool = False   # True → PDF avec un bandeau titre par section (export_visite_to_pdf), comme l'onglet

    @property
    def nb_lignes(self) -> int:
        return sum(len(df) for _, df in self.sections)


def evolution_pct(p1: float, p2: float) -> float:
    """Évolution de P1 à P2 en %. Le CA peut être négatif (avoirs Sage) :
    P1 = 0 → +100 % / −100 % / 0 % selon le signe de P2 ; sinon (P2 − P1) ÷ |P1| × 100,
    pour qu'une hausse reste positive même quand P1 est négatif."""
    if p1 == 0:
        return 0.0 if p2 == 0 else (100.0 if p2 > 0 else -100.0)
    return (p2 - p1) / abs(p1) * 100


_GROUP_LABELS = {"client": "Client", "region": "Région", "commercial": "Collaborateur"}


def _sous_titre_genere(extra: str = "") -> str:
    return f"Généré le {date.today().isoformat()}{extra}"


# ---------------------------------------------------------------------------
# Onglet 1 : Chiffre d'Affaire
# ---------------------------------------------------------------------------
_CA_RATIO_COLS = {"ca_ht": "CA HT", "nb_factures": "Nb Factures",
                  "moyenne_facture": "Moyenne / Facture", "pct_ca": "% du CA"}
_CA_RENAME = {
    "client":     {"do_tiers": "Code Client", "ct_intitule": "Nom Client"},
    "region":     {"ct_coderegion": "Région"},
    "commercial": {"co_no": "Code Collab.", "co_fullname": "Collaborateur"},
}


def rapport_ca(rows: list, group_by: str, date_from: str, date_to: str) -> Rapport:
    """CA HT groupé par client, région ou commercial."""
    df = pd.DataFrame(rows)
    rename_map = {**_CA_RENAME[group_by], **_CA_RATIO_COLS}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return Rapport(
        nom="chiffre_affaire",
        titre=f"Rapport CA par {_GROUP_LABELS[group_by]}",
        sous_titre=f"Période : {date_from} au {date_to}",
        sections=[("Chiffre d'Affaire", df)],
    )


# ---------------------------------------------------------------------------
# Onglet 2 : Comparaison CA
# ---------------------------------------------------------------------------
_CMP_JOIN = {
    "client":     (["do_tiers"], {"do_tiers": "Code", "ct_intitule": "Nom"}),
    "region":     (["ct_coderegion"], {"ct_coderegion": "Région"}),
    "commercial": (["co_no"], {"co_no": "Code", "co_fullname": "Collaborateur"}),
}
_CMP_ORDER = {
    "client":     ["Code", "Nom Client", "CA Période 1", "CA Période 2", "Ecart (MAD)", "Evolution (%)"],
    "commercial": ["Code", "Nom Collaborateur", "CA Période 1", "CA Période 2", "Ecart (MAD)", "Evolution (%)"],
    "region":     ["Région", "CA Période 1", "CA Période 2", "Ecart (MAD)", "Evolution (%)"],
}


def rapport_comparaison_ca(rows_p1: list, rows_p2: list, group_by: str, periode_1: tuple, periode_2: tuple) -> Rapport:
    """CA HT de la période 1 (référence) face à la période 2, avec écart et évolution."""
    df1, df2 = pd.DataFrame(rows_p1), pd.DataFrame(rows_p2)
    join_keys, col_name_mapping = _CMP_JOIN[group_by]
    col_name_mapping = dict(col_name_mapping)

    if not df1.empty and not df2.empty:
        join_keys = [k for k in join_keys if k in df1.columns and k in df2.columns]
    if df1.empty:
        df1 = pd.DataFrame(columns=join_keys + ["ca_ht"])
    if df2.empty:
        df2 = pd.DataFrame(columns=join_keys + ["ca_ht"])

    df_merged = pd.merge(df1, df2, on=join_keys, how="outer", suffixes=('_p1', '_p2'))

    if 'co_fullname_p1' in df_merged.columns and 'co_fullname_p2' in df_merged.columns:
        df_merged['co_fullname'] = df_merged['co_fullname_p2'].fillna(df_merged['co_fullname_p1'])
        df_merged = df_merged.drop(columns=['co_fullname_p1', 'co_fullname_p2'])
        col_name_mapping['co_fullname'] = 'Nom Collaborateur'

    if 'ct_intitule_p1' in df_merged.columns and 'ct_intitule_p2' in df_merged.columns:
        df_merged['ct_intitule'] = df_merged['ct_intitule_p2'].fillna(df_merged['ct_intitule_p1'])
        df_merged = df_merged.drop(columns=['ct_intitule_p1', 'ct_intitule_p2'])
        col_name_mapping['ct_intitule'] = 'Nom Client'

    df_merged = df_merged.fillna(0)
    df_merged['Ecart (MAD)'] = df_merged['ca_ht_p2'] - df_merged['ca_ht_p1']
    df_merged['Evolution (%)'] = [evolution_pct(p1, p2) for p1, p2 in zip(df_merged['ca_ht_p1'], df_merged['ca_ht_p2'])]

    rename_dict = {**col_name_mapping, "ca_ht_p1": "CA Période 1", "ca_ht_p2": "CA Période 2"}
    df_show = df_merged.rename(columns=rename_dict)

    if group_by == "commercial":
        for col in ["Nom Collaborateur", "Code"]:
            if col in df_show.columns:
                df_show[col] = df_show[col].replace({0: "Non identifié", "0": "Non identifié", "": "Non identifié"})

    df_show = df_show[[c for c in _CMP_ORDER[group_by] if c in df_show.columns]]

    return Rapport(
        nom="comparaison_ca",
        titre=f"Comparaison CA par {_GROUP_LABELS[group_by]}",
        sous_titre=(
            f"Période 1 : {periode_1[0]} au {periode_1[1]}  |  "
            f"Période 2 : {periode_2[0]} au {periode_2[1]}"
        ),
        sections=[("Comparaison CA", df_show)],
    )


# ---------------------------------------------------------------------------
# Onglets 3 et 9 : Balance / Balance Âgée (filtre commercial)
# ---------------------------------------------------------------------------
def _filtre_commercial(df: pd.DataFrame, code: Optional[int]) -> tuple:
    """Garde les lignes du commercial `code` (F_DOCENTETE.co_no, 0 = Non identifié) ;
    retourne (df filtré, libellé du commercial ou "Tout")."""
    if code is None or df.empty or "Code Commercial" not in df.columns:
        return df, "Tout"
    df = df[df["Code Commercial"] == code].copy()
    if df.empty:
        logger.warning("Aucune ligne pour le commercial %s", code)
        return df, str(code)
    return df, str(df["Commercial"].iloc[0])


def _non_identifie(df: pd.DataFrame) -> pd.DataFrame:
    if 'Nom Client' in df.columns:
        df['Nom Client'] = df['Nom Client'].replace({0: "Non Identifier", "0": "Non Identifier", "": "Non Identifier"})
    return df


def rapport_balance(rows: list, commercial: Optional[int] = None) -> Rapport:
    """Balance par clients : A Nouveau, un mois par colonne, En Cours, Totale."""
    df, libelle = _filtre_commercial(pd.DataFrame(rows), commercial)
    if not df.empty:
        df = _non_identifie(df)
        # Identifiants, puis mois (ordre de l'API, du plus ancien au plus récent), puis totaux.
        # "Code Commercial" ne sert qu'au filtre.
        fixed_debut = ["Ref Client", "Nom Client", "Commercial", "A Nouveau"]
        fixed_fin = ["En Cours", "Totale"]
        mois_cols = [c for c in df.columns if c not in fixed_debut + fixed_fin + ["Code Commercial"]]
        df = df[[c for c in fixed_debut + mois_cols + fixed_fin if c in df.columns]]
    return Rapport(
        nom="balance",
        titre="Balance par Clients",
        sous_titre=_sous_titre_genere(f" - Commercial : {libelle}" if libelle != "Tout" else ""),
        sections=[("Balance par Clients", df)],
    )


def rapport_balance_agee(rows: list, commercial: Optional[int] = None) -> Rapport:
    """Balance âgée par clients : tranches 0-60j / 60-90j / 90-120j / +120j."""
    df, libelle = _filtre_commercial(pd.DataFrame(rows), commercial)
    if not df.empty:
        df = _non_identifie(df)
        desired_cols = ["Ref Client", "Nom Client", "Commercial", "0-60j", "60-90j", "90-120j", "+120j", "Totale"]
        df = df[[c for c in desired_cols if c in df.columns]]
    return Rapport(
        nom="balance_agee",
        titre="Rapport Balance Âgée",
        sous_titre=_sous_titre_genere(f" - Commercial : {libelle}" if libelle != "Tout" else ""),
        sections=[("Balance Âgée par Clients", df)],
        pdf_par_section=True,
    )


# ---------------------------------------------------------------------------
# Onglet 4 : Valeur du Stock (filtres dépôt / famille / article)
# ---------------------------------------------------------------------------
_VALSTOCK_RENAME = {
    "de_intitule": "Dépôt",
    "fa_intitule": "Famille",
    "ar_ref": "Réf. Article",
    "ar_design": "Désignation",
    "qte_stock": "Qté Stock",
    "prix_revient": "Coût moyen achat",
    "valeur_stock": "Valeur Stock",
}


def _filtre_liste(df: pd.DataFrame, col: str, valeurs: Optional[list], libelle: str) -> pd.DataFrame:
    if not valeurs:
        return df
    absentes = set(valeurs) - set(df[col].dropna().astype(str))
    if absentes:
        logger.warning("Valeur stock : %s sans stock dans la sélection : %s", libelle, ", ".join(sorted(absentes)))
    return df[df[col].astype(str).isin(valeurs)]


def rapport_valeur_stock(rows: list, depots: Optional[list] = None, familles: Optional[list] = None,
                         articles: Optional[list] = None) -> Rapport:
    """Valeur du stock par dépôt / famille / article, triée par valeur décroissante.
    Filtres : listes d'intitulés (de_intitule, fa_intitule, ar_design) — absent = tous."""
    df = pd.DataFrame(rows)
    if df.empty:
        df_show = pd.DataFrame(columns=list(_VALSTOCK_RENAME.values()))
    else:
        for c in ["qte_stock", "prix_revient", "valeur_stock"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        df = _filtre_liste(df, "de_intitule", depots, "dépôt(s)")
        df = _filtre_liste(df, "fa_intitule", familles, "famille(s)")
        df = _filtre_liste(df, "ar_design", articles, "article(s)")
        df_show = df[list(_VALSTOCK_RENAME)].rename(columns=_VALSTOCK_RENAME)
        df_show = df_show.sort_values("Valeur Stock", ascending=False)

    def _libelle(valeurs):
        return ", ".join(valeurs) if valeurs else "Tous"

    return Rapport(
        nom="valeur_stock",
        titre="Valeur du Stock",
        sous_titre=f"Dépôts : {_libelle(depots)} | Familles : {_libelle(familles)} | Articles : {_libelle(articles)}",
        sections=[("Valeur du Stock", df_show)],
    )


# ---------------------------------------------------------------------------
# Onglet 5 : Avant Visite Client
# ---------------------------------------------------------------------------
_VISITE_SECTIONS = {
    "bc_en_cours":          "1-BCs en cours",
    "factures_non_reglees": "2-Factures impayées",
    "articles_par_mois":    "3-Articles par mois",
    "familles_actives":     "4-Familles actives",
    "familles_dormantes":   "5-Familles dormantes",
    "familles_mortes":      "6-Familles jamais vendues",
    "comparaison_ca":       "7-Comparaison CA",
}


def rapport_visite_client(data: dict, code_client: str, nom_client: str) -> Rapport:
    """Rapport avant visite d'un client Sage (7 sections)."""
    sections = [
        (label, pd.DataFrame(data.get(key) or []))
        for key, label in _VISITE_SECTIONS.items()
    ]
    return Rapport(
        nom=f"visite_client_{re.sub(r'[^A-Za-z0-9_-]', '_', code_client)}",
        titre=f"Rapport Avant Visite - {code_client} — {nom_client}",
        sous_titre=f"Client : {code_client} — Généré le {date.today().isoformat()}",
        sections=sections,
        pdf_par_section=True,
    )


# ---------------------------------------------------------------------------
# Onglet 6 : Produits Dormants
# ---------------------------------------------------------------------------
_DORMANT_RENAME = {
    "ar_ref": "Réf. Article", "ar_design": "Désignation",
    "fa_intitule": "Famille", "de_intitule": "Dépôt",
    "quantite_totale": "Qté Totale",
    "prix_achat": "Prix Achat",
    "valeur_stock": "Valeur Stock",
    "derniere_date_vente": "Dernière Vente",
    "nbr_jours_inactif": "Mois Inactivité",
}


def rapport_dormants(rows: list, mois: int) -> Rapport:
    """Produits sans vente depuis plus de `mois` mois."""
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.rename(columns={k: v for k, v in _DORMANT_RENAME.items() if k in df.columns})
        cols = [v for v in _DORMANT_RENAME.values() if v in df.columns]
        df = df[cols] if cols else df

        for c in ["Prix Achat", "Valeur Stock", "Qté Totale"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        if "Dernière Vente" in df.columns:
            df["Dernière Vente"] = pd.to_datetime(df["Dernière Vente"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
        if "Mois Inactivité" in df.columns:
            df["Mois Inactivité"] = df["Mois Inactivité"].apply(
                lambda x: "Jamais vendu" if pd.isna(x) or x == 999999 else f"{round(float(x) / 30)} mois"
            )
    return Rapport(
        nom="produits_dormants",
        titre="Rapport Produits Dormants",
        sous_titre=f"Inactivite > {mois} mois",
        sections=[(f"Produits Dormants (inactifs > {mois} mois)", df)],
        pdf_par_section=True,
    )


# ---------------------------------------------------------------------------
# Onglet 7 : Lots en Péremption
# ---------------------------------------------------------------------------
_PEREMPTION_RENAME = {
    "ar_ref": "Réf. Article", "ar_design": "Désignation",
    "fa_intitule": "Famille",
    "ls_noserie": "N° Lot/Série", "ls_qterestant": "Qté Restante",
    "ls_peremption": "Date Péremption", "jours_restants": "Jours Restants",
}


def rapport_peremption(rows: list, expiry_days: int) -> Rapport:
    """Lots expirant dans les `expiry_days` prochains jours."""
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.rename(columns={k: v for k, v in _PEREMPTION_RENAME.items() if k in df.columns})
        cols = [v for v in _PEREMPTION_RENAME.values() if v in df.columns]
        df = df[cols] if cols else df
    return Rapport(
        nom="lots_peremption",
        titre="Rapport Lots en Peremption",
        sous_titre=f"Expiration dans les {expiry_days} prochains jours",
        sections=[(f"Lots en Peremption (< {expiry_days} jours)", df)],
        pdf_par_section=True,
    )


# ---------------------------------------------------------------------------
# Onglet 8 : Consommation par Produit
# ---------------------------------------------------------------------------
def rapport_consommation(data: dict) -> Rapport:
    """Consommation des 6 derniers mois : récapitulatif par famille + détail par article."""
    return Rapport(
        nom="consommation",
        titre="Rapport Consommation par Produit",
        sous_titre=f"6 derniers mois — Généré le {date.today().isoformat()}",
        sections=[
            ("Recap par Famille", pd.DataFrame(data.get("par_famille") or [])),
            ("Detail par Article", pd.DataFrame(data.get("par_article") or [])),
        ],
        pdf_par_section=True,
    )
