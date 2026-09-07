from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import uuid

def get_real_ip(request: Request):
    # Bypass du rate limiter pour l'agent Telegram : on lui donne une clé unique à chaque requête
    if request.url.path.startswith("/telegram"):
        return str(uuid.uuid4())
        
    # Ordre de priorité : Cloudflare > Proxy > Direct
    for header in ["CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP"]:
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

limiter = Limiter(key_func=get_real_ip)
