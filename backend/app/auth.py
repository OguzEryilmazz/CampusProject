"""Supabase oturumunu (JWT) doğrulayan FastAPI bağımlılığı.

Token, Supabase Auth'un /auth/v1/user uç noktasına sorulur. Bu, imza algoritmasından
bağımsız çalışır. Sonuç 60 sn önbelleğe alınır, her istekte Supabase'e gidilmez.
(Çıkış yapılan bir token en fazla 60 sn daha geçerli sayılır.)
"""
import time

import httpx
from fastapi import Header, HTTPException

from .config import supabase_anon_key, supabase_url

_TTL = 60
_CACHE = {}  # token -> (bitiş zamanı, kullanıcı)
_http = httpx.AsyncClient(timeout=10)


async def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Giriş gerekli")
    token = authorization[7:].strip()
    now = time.monotonic()

    hit = _CACHE.get(token)
    if hit and hit[0] > now:
        return hit[1]

    url, key = supabase_url(), supabase_anon_key()
    if not url or not key:
        raise HTTPException(500, "Supabase ayarı eksik")
    try:
        r = await _http.get(
            f"{url}/auth/v1/user",
            headers={"apikey": key, "Authorization": f"Bearer {token}"},
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Kimlik doğrulama servisine ulaşılamadı")
    if r.status_code != 200:
        raise HTTPException(401, "Geçersiz ya da süresi dolmuş oturum")

    body = r.json()
    user = {"id": body["id"], "email": body.get("email")}
    if len(_CACHE) > 1000:  # süresi dolanları temizle
        for t in [t for t, (exp, _) in _CACHE.items() if exp <= now]:
            del _CACHE[t]
    _CACHE[token] = (now + _TTL, user)
    return user