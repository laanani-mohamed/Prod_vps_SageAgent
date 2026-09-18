"""
config.py — Configuration de l'app d'observabilité ETL (dashboard_ops).
"""
import os
from dotenv import load_dotenv

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_APP_ROOT, ".env"))

OPS_DASHBOARD_PASSWORD = os.getenv("OPS_DASHBOARD_PASSWORD")

PAGE_TITLE = "SageAgent — Observabilité ETL"
