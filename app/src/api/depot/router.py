"""
api/depot/router.py — Dépôt des 11 fichiers Sage depuis le front (page « Dépôt des fichiers », directeur).

S'insère dans le circuit SFTP existant, sans le modifier :
  1. Chaque fichier reçu attend dans upload/<DOSSIER>/.depot_web/ : sous-dossier caché, ignoré par le watcher,
     la file d'attente et l'archivage de l'ETL. Seul le nom est contrôlé (l'un des 11 de FILE_TABLE_MAP, casse libre).
  2. « Envoyer » déplace les 11 fichiers d'un coup (rename, même montage) dans upload/<DOSSIER>/ : l'ETL les traite
     alors exactement comme un dépôt SFTP (contrôles, chargement, archivage, rapport ERREUR_*.txt).
  3. Suivi : événements du dernier chargement (etl_events.pipeline_events) et son rapport ERREUR_*.txt.

  GET    /api/depot/etat                → fichiers reçus, dossier SFTP, dernier chargement (étapes, erreur)
  PUT    /api/depot/fichiers/{nom}      → reçoit un fichier (corps brut, en flux)
  DELETE /api/depot/fichiers/{nom}      → retire un fichier reçu
  POST   /api/depot/envoyer             → transmet les 11 fichiers au traitement
  GET    /api/depot/rapport?run_id=…    → rapport d'erreur d'un chargement (texte)
"""
import glob
import os
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from api._base_router import secured_handle
from api.auth.dependencies import DIRECTEUR_SEUL
from api.auth.schemas import TokenData
from api.db import get_db_connection
from config.etl_config import ERROR_REPORT_PREFIX, QUEUE_DIR, UPLOAD_BASE_PATH
from map_data.reference.file_table_map import FILE_TABLE_MAP

router = APIRouter(prefix="/api/depot", tags=["Dépôt des fichiers Sage"])

ATTENDUS = {n.upper(): n for n in FILE_TABLE_MAP}   # NOM EN MAJUSCULES → nom attendu (F_DOCLIGNE.txt)
ATTENTE = ".depot_web"
DUREE_ATTENTE = 24 * 3600     # fichier reçu jamais envoyé : supprimé (évite de mélanger deux exports)
TAILLE_MAX = 2 * 1024 ** 3    # par fichier (F_DOCLIGNE de CROSS : 173 Mo)

# Étapes du suivi affichées par la page : 0 envoi, 1 prise en charge, 2 contrôle, 3 chargement, 4 terminé.
# Événement qui termine chaque étape, puis étape arrêtée par chaque événement d'échec.
FIN_ETAPE = {"RunInitialized": 1, "SchemaValidationPassed": 2, "IngestionCompleted": 3, "PipelineCompleted": 4}
ECHEC_ETAPE = {"WatcherValidationFailed": 1, "FilenameValidationFailed": 2, "SizeValidationFailed": 2,
               "SchemaValidationFailed": 2, "IngestionFailed": 3}

_SQL_DERNIER = """
    SELECT run_id::text, event_type, payload, created_at FROM etl_events.pipeline_events
    WHERE run_id = (SELECT run_id FROM etl_events.pipeline_events WHERE lower(client) = lower(%(d)s) ORDER BY id DESC LIMIT 1)
    ORDER BY id
"""
_SQL_REUSSI = """SELECT MAX(created_at) FROM etl_events.pipeline_events
                 WHERE lower(client) = lower(%(d)s) AND event_type = 'PipelineCompleted'"""


def _dossier(schema: str) -> str:
    """Dossier SFTP du client (CROSS pour le schéma cross ; l'ETL charge le dossier X dans le schéma x)."""
    noms = sorted(d for d in os.listdir(UPLOAD_BASE_PATH)
                  if d.lower() == schema.lower() and os.path.isdir(os.path.join(UPLOAD_BASE_PATH, d)))
    if not noms:
        raise HTTPException(404, "Aucun dossier de dépôt pour ce client")
    return noms[0]


def _attente(dossier: str) -> str:
    chemin = os.path.join(UPLOAD_BASE_PATH, dossier, ATTENTE)
    os.makedirs(chemin, exist_ok=True)
    return chemin


def _nom(nom: str) -> str:
    """Nom attendu correspondant (casse libre), sinon 400. Empêche aussi tout chemin hors du dossier."""
    if nom.upper() not in ATTENDUS:
        raise HTTPException(400, f"Nom de fichier non reconnu : {nom}")
    return ATTENDUS[nom.upper()]


def _recus(attente: str) -> dict:
    """Fichiers reçus en attente d'envoi ; ceux de plus de 24 h (et envois interrompus) sont supprimés."""
    recus = {}
    for f in os.listdir(attente):
        st = os.stat(os.path.join(attente, f))
        if time.time() - st.st_mtime > DUREE_ATTENTE:
            os.remove(os.path.join(attente, f))
        elif f in FILE_TABLE_MAP:
            recus[f] = {"nom": f, "taille": st.st_size, "recu_le": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()}
    return recus


def _dans_dossier(dossier: str) -> list:
    """Fichiers présents dans le dossier SFTP : dépôt SFTP en cours, ou envoi pas encore pris par l'ETL (≤ 20 s)."""
    d = os.path.join(UPLOAD_BASE_PATH, dossier)
    return [f for f in os.listdir(d) if not f.startswith((".", ERROR_REPORT_PREFIX)) and os.path.isfile(os.path.join(d, f))]


def _en_file(dossier: str) -> bool:
    """Dépôt en file d'attente ou en cours de traitement par l'ETL (queue/<DOSSIER>__<horodatage>/)."""
    return bool(glob.glob(os.path.join(QUEUE_DIR, f"{glob.escape(dossier)}__*")))


def _rapport(dossier: str, run_id: str):
    """Rapport ERREUR_*.txt du chargement `run_id` déposé par l'ETL dans le dossier du client : (nom, texte)."""
    for chemin in sorted(glob.glob(os.path.join(UPLOAD_BASE_PATH, dossier, ERROR_REPORT_PREFIX + "*.txt")), reverse=True)[:30]:
        with open(chemin, encoding="utf-8", errors="replace") as f:
            texte = f.read()
        if f"run_id: {run_id}" in texte:
            return os.path.basename(chemin), texte
    return None, None


def _erreur(dossier: str, run_id: str, code: str) -> dict:
    """Détail de l'échec lu dans le rapport (texte de etl/reporting/error_report.py, celui que lit le client)."""
    nom, texte = _rapport(dossier, run_id)
    def champ(motif):
        m = texte and re.search(motif, texte, re.M)
        return m.group(1).strip() if m else None
    return {
        "code": champ(r"^error_code: (.+)$") or code, "rapport": nom is not None,
        "fichier": champ(r"^Fichier concerné : (.+)$"), "ligne": champ(r"^Ligne concernée\s*: (.+)$"),
        "colonne": champ(r"^Colonne concernée : (.+)$"),
        "probleme": champ(r"^Problème : ([\s\S]+?)\n\nQue faire"), "que_faire": champ(r"^Que faire :\n\s*(.+)$"),
    }


def _etat(client_schema: str) -> dict:
    dossier = _dossier(client_schema)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(_SQL_DERNIER, {"d": dossier})
        evenements = cur.fetchall()
        cur.execute(_SQL_REUSSI, {"d": dossier})
        reussi = cur.fetchone()[0]

    dernier = None
    if evenements:
        etapes, echec, code = [None] * 5, None, None
        for _, type_, payload, quand in evenements:
            if type_ in FIN_ETAPE:
                etapes[FIN_ETAPE[type_]] = quand.isoformat()
            if type_ in ECHEC_ETAPE or type_ == "PipelineFailed":
                code = code or (payload or {}).get("error_code")
                if echec is None:   # PipelineFailed seul (erreur inattendue) : arrêt à la 1re étape non terminée
                    echec = ECHEC_ETAPE.get(type_) or next((k for k in range(1, 5) if etapes[k] is None), 4)
        dernier = {
            "run_id": evenements[0][0], "debut": evenements[0][3].isoformat(), "fin": evenements[-1][3].isoformat(),
            "statut": "reussi" if etapes[4] else "echec" if echec else "en_cours",
            "etapes": etapes, "echec": echec, "erreur": _erreur(dossier, evenements[0][0], code) if echec else None,
        }
    return {
        "dossier": dossier, "attendus": list(FILE_TABLE_MAP), "recus": list(_recus(_attente(dossier)).values()),
        "sftp": len(_dans_dossier(dossier)), "en_file": _en_file(dossier),
        "dernier": dernier, "dernier_reussi": reussi.isoformat() if reussi else None,
    }


def _preparer(client_schema: str, nom: str) -> tuple:
    """Chemins (temporaire caché unique, final) du fichier à recevoir."""
    nom, attente = _nom(nom), _attente(_dossier(client_schema))
    return os.path.join(attente, f".{nom}.{uuid.uuid4().hex}.part"), os.path.join(attente, nom)


def _retirer(client_schema: str, nom: str) -> dict:
    chemin = os.path.join(_attente(_dossier(client_schema)), _nom(nom))
    if os.path.exists(chemin):
        os.remove(chemin)
    return {"retire": _nom(nom)}


def _envoyer(client_schema: str) -> dict:
    dossier = _dossier(client_schema)
    attente, cible = _attente(dossier), os.path.join(UPLOAD_BASE_PATH, dossier)
    recus = _recus(attente)
    if len(recus) != len(FILE_TABLE_MAP):
        raise HTTPException(400, f"{len(FILE_TABLE_MAP) - len(recus)} fichier(s) manquant(s)")
    if _dans_dossier(dossier):
        raise HTTPException(409, f"Le dossier {dossier} contient déjà des fichiers (dépôt SFTP en cours)")
    if _en_file(dossier):
        raise HTTPException(409, "Un chargement est déjà en cours")
    for nom in recus:
        source = os.path.join(attente, nom)
        # Date de modification remise à maintenant : le watcher attend 5 s de stabilité avant de compter les fichiers,
        # il ne peut donc pas voir un envoi à moitié déplacé (ni le rejeter comme dépôt incomplet trop ancien).
        os.utime(source)
        os.rename(source, os.path.join(cible, nom))
    return {"envoye_le": datetime.now(timezone.utc).isoformat()}


def _texte_rapport(client_schema: str, run_id: str):
    nom, texte = _rapport(_dossier(client_schema), run_id)
    if texte is None:
        raise HTTPException(404, "Rapport d'erreur introuvable")
    return PlainTextResponse(texte, headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@router.get("/etat", summary="État du dépôt : fichiers reçus, dossier SFTP, dernier chargement")
def etat(request: Request, client_schema: str = Query(...), current_user: TokenData = Depends(DIRECTEUR_SEUL)):
    return secured_handle(_etat, "/api/depot/etat", request, current_user, client_schema)


@router.put("/fichiers/{nom}", summary="Reçoit un fichier Sage (corps brut)")
async def recevoir(nom: str, request: Request, client_schema: str = Query(...), current_user: TokenData = Depends(DIRECTEUR_SEUL)):
    # Endpoint en flux : le jeton et le nom sont vérifiés avant de lire le corps (F_DOCLIGNE : plus de 170 Mo).
    temporaire, final = secured_handle(_preparer, f"/api/depot/fichiers/{nom}", request, current_user, client_schema, nom=nom)
    taille = 0
    try:
        with open(temporaire, "wb") as f:
            async for morceau in request.stream():
                taille += len(morceau)
                if taille > TAILLE_MAX:
                    raise HTTPException(413, "Fichier trop volumineux")
                f.write(morceau)
        os.replace(temporaire, final)
    finally:
        if os.path.exists(temporaire):
            os.remove(temporaire)
    return {"nom": os.path.basename(final), "taille": taille}


@router.delete("/fichiers/{nom}", summary="Retire un fichier reçu")
def retirer(nom: str, request: Request, client_schema: str = Query(...), current_user: TokenData = Depends(DIRECTEUR_SEUL)):
    return secured_handle(_retirer, f"/api/depot/fichiers/{nom}", request, current_user, client_schema, nom=nom)


@router.post("/envoyer", summary="Transmet les 11 fichiers reçus au traitement ETL")
def envoyer(request: Request, client_schema: str = Query(...), current_user: TokenData = Depends(DIRECTEUR_SEUL)):
    return secured_handle(_envoyer, "/api/depot/envoyer", request, current_user, client_schema)


@router.get("/rapport", summary="Rapport d'erreur (ERREUR_*.txt) d'un chargement")
def rapport(request: Request, run_id: str = Query(..., pattern=r"^[0-9a-f-]{36}$"), client_schema: str = Query(...),
            current_user: TokenData = Depends(DIRECTEUR_SEUL)):
    return secured_handle(_texte_rapport, "/api/depot/rapport", request, current_user, client_schema, run_id=run_id)
