"""
bi/referentiel/business_logic/validators.py
"""
def require_filter(req, filter_name: str, msg: str):
    if not getattr(req, filter_name, None):
        raise ValueError(msg)

def hard_limit(value: int, max_limit: int = 5000) -> int:
    return min(value, max_limit)
