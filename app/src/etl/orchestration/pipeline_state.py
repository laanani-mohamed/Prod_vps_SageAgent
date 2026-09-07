"""
pipeline_state.py — Wrapper de compatibilité vers l'Event Store.

Ce module conserve les mêmes signatures de fonctions qu'avant (init_state,
update_step, fail_state, complete_state) pour assurer la compatibilité avec
main.py, mais délègue maintenant TOUTE la logique à event_store.py.

La source de vérité n'est plus un fichier JSON écrasable.
La source de vérité est désormais la table PostgreSQL `etl_events.pipeline_events`.

Pour reconstruire l'état complet d'un run depuis ses événements, utilisez :
    from etl.orchestration.event_store import rebuild_state
    state = rebuild_state(run_id)
"""

import logging
from etl.orchestration.event_store import append_event

logger = logging.getLogger("etl.pipeline_state")


def init_state(run_id: str, client: str):
    """
    Démarre le suivi d'un nouveau run de pipeline.
    Émet l'événement : RunInitialized.
    """
    logger.debug(
        f"[State] Initialisation du run {run_id} pour le client {client}.",
        extra={"run_id": run_id, "client": client, "step": "state_init"}
    )
    append_event(
        run_id=run_id,
        client=client,
        event_type="RunInitialized",
        payload={"client": client}
    )


def update_step(run_id: str, client: str, step_name: str, status: str, next_step: str = None):
    """
    Enregistre la transition d'une étape du pipeline.

    Mapping step_name + status → event_type :
      validation  + SUCCESS → SchemaValidationPassed  (étape finale de validation)
      ingestion   + SUCCESS → IngestionCompleted
      archivage   + SUCCESS → ArchiveCompleted
    """
    mapping = {
        ("validation", "SUCCESS"):  "SchemaValidationPassed",
        ("ingestion",  "SUCCESS"):  "IngestionCompleted",
        ("archivage",  "SUCCESS"):  "ArchiveCompleted",
    }
    event_type = mapping.get((step_name, status), f"StepUpdated_{step_name}_{status}")

    payload = {"step": step_name, "status": status}
    if next_step:
        payload["next_step"] = next_step

    append_event(run_id=run_id, client=client, event_type=event_type, payload=payload)


def fail_state(run_id: str, client: str, step_name: str, error_code: str, error_message: str):
    """
    Marque le pipeline comme en échec.
    Émet l'événement : PipelineFailed.
    """
    logger.debug(
        f"[State] Run {run_id} — Échec à l'étape '{step_name}' : {error_code}.",
        extra={"run_id": run_id, "client": client, "step": "state_fail",
               "error_code": error_code}
    )
    append_event(
        run_id=run_id,
        client=client,
        event_type="PipelineFailed",
        payload={
            "step":          step_name,
            "error_code":    error_code,
            "error_message": error_message
        }
    )


def complete_state(run_id: str, client: str):
    """
    Marque le pipeline comme terminé avec succès.
    Émet l'événement : PipelineCompleted.
    """
    logger.debug(
        f"[State] Run {run_id} — Pipeline complété avec succès.",
        extra={"run_id": run_id, "client": client, "step": "state_complete"}
    )
    append_event(
        run_id=run_id,
        client=client,
        event_type="PipelineCompleted",
        payload={"client": client}
    )
