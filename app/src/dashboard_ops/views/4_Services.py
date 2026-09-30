"""Page 4 — État des services, file d'attente, stockage et purge (lecture seule)."""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from services.system_status import list_services, queue_status, disk_usage, storage_folders, purge_status
from components.formatting import fmt_taille, fmt_entier

st.title("Services & stockage")
if st.button("🔄 Actualiser"):
    st.cache_data.clear()


@st.cache_data(ttl=60)
def _services():
    return list_services()


@st.cache_data(ttl=300)
def _stockage():
    return storage_folders(), disk_usage(), purge_status()


# --- Services ---------------------------------------------------------------
st.markdown("### Services")
services = _services()
now = datetime.now(timezone.utc)
if not services:
    st.warning("Aucun service SageAgent trouvé via systemctl.")
else:
    inactifs = [s["service"] for s in services if not s["actif"]]
    redemarres = [s["service"] for s in services if s["depuis"] and s["depuis"].date() == now.date()]
    if inactifs:
        st.error("❌ Service(s) arrêté(s) : " + ", ".join(inactifs))
    if redemarres:
        st.warning("🔁 Redémarré(s) aujourd'hui (UTC) : " + ", ".join(redemarres)
                   + " — le code en cours d'exécution est celui du disque à cette heure-là.")
    st.dataframe(pd.DataFrame([{
        "Service": s["service"],
        "État": ("✅ " if s["actif"] else "❌ ") + s["etat"],
        "Démarré le (UTC)": s["depuis"].strftime("%Y-%m-%d %H:%M") if s["depuis"] else "—",
        "Actif depuis": f"{(now - s['depuis']).days} j {(now - s['depuis']).seconds // 3600} h" if s["depuis"] else "—",
        "Redémarrages auto": s["redemarrages_auto"],
        "Description": s["description"],
    } for s in services]), width="stretch", hide_index=True)
st.caption("Le dashboard_ops lui-même n'est pas un service systemd (lancé via nohup) : il tourne, puisque cette page s'affiche.")

# --- File d'attente ----------------------------------------------------------
st.markdown("### File d'attente ETL")
q = queue_status()
q1, q2 = st.columns(2)
q1.metric("Dossiers dans queue", q["queue"])
q2.metric("Dossiers dans broker_queue", q["broker_queue"])

# --- Stockage ----------------------------------------------------------------
folders, disk, purge = _stockage()
st.markdown("### Stockage")
d1, d2, d3 = st.columns(3)
d1.metric("Disque utilisé", f"{fmt_taille(disk['utilise'])} / {fmt_taille(disk['total'])}")
d2.metric("Espace libre", fmt_taille(disk["libre"]))
d3.metric("Taux d'occupation", f"{disk['utilise'] / disk['total'] * 100:.0f} %")
st.dataframe(pd.DataFrame([{
    "Dossier (storage_srv)": f["dossier"],
    "Taille": fmt_taille(f["taille"]),
    "Fichiers": fmt_entier(f["fichiers"]),
    "Plus ancien fichier": f["plus_ancien"].strftime("%Y-%m-%d") if f["plus_ancien"] else "—",
    "Âge (jours)": (now - f["plus_ancien"]).days if f["plus_ancien"] else None,
} for f in folders]), width="stretch", hide_index=True)

# --- Purge -------------------------------------------------------------------
st.markdown("### Purge des archives")
retention = purge["retention_jours"]
trop_vieux = [f["dossier"] for f in folders
              if f["dossier"] in ("archives", "error") and f["plus_ancien"] and (now - f["plus_ancien"]).days > retention]
problemes = []
if not purge["planifie"]:
    problemes.append("aucune tâche cron ne lance la purge")
for s in purge["scripts"]:
    if not s["cible_valide"]:
        problemes.append(f"`{s['script'].split('/app/')[-1]}` vise `{s['cible']}` au lieu de `{purge['chemin_attendu']}`")
if trop_vieux:
    problemes.append(f"fichiers de plus de {retention} jours dans : {', '.join(trop_vieux)}")

p1, p2 = st.columns(2)
p1.metric("Dernière purge enregistrée", purge["derniere_purge"].strftime("%Y-%m-%d %H:%M") if purge["derniere_purge"] else "Jamais")
p2.metric("Rétention prévue", f"{retention} jours")
if problemes:
    st.error("❌ La purge ne fonctionne pas :\n\n" + "\n".join(f"- {p}" for p in problemes))
else:
    st.success("✅ Purge planifiée, chemins corrects, aucun fichier au-delà de la rétention.")
