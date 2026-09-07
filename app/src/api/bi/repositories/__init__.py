"""
api/bi/repositories/__init__.py
"""
from api.bi.repositories.factory_repo import get_bi_repo
from api.bi.repositories.base_bi_repo import BaseBIRepository

__all__ = ["get_bi_repo", "BaseBIRepository"]
