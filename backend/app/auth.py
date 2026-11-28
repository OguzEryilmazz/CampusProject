"""Supabase oturumunu (JWT) doğrulayan FastAPI bağımlılığı.

Token, Supabase Auth'un /auth/v1/user uç noktasına sorulur. Bu, imza algoritmasından
bağımsız çalışır. Sonuç 60 sn önbelleğe alınır, her istekte Supabase'e gidilmez.
(Çıkış yapılan bir token en fazla 60 sn daha geçerli sayılır.)
"""
import time

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from .config import supabase_anon_key, supabase_url

_TTL = 60
_CACHE = {}  # token -> (bitiş zamanı, kullanıcı)
_http = httpx.AsyncClient(timeout=10)


# /docs sayfasındaki "Authorize" düğmesi bu şemayı kullanır: e-posta ve şifre girilir,
# token otomatik alınıp tüm isteklere eklenir.
oauth2 = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


async def password_login(email, password):
    """Supabase Auth ile e-posta/şifre girişi yapar, erişim token'ını döndürür."""
    url, key = supabase_url(), supabase_anon_key()
    if not url or not key:
        raise HTTPException(500, "Supabase ayarı eksik")
    try:
        r = await _http.post(f"{url}/auth/v1/token", params={"grant_type": "password"},
                             headers={"apikey": key}, json={"email": email, "password": password})
    except httpx.HTTPError:
        raise HTTPException(503, "Kimlik doğrulama servisine ulaşılamadı")
    if r.status_code != 200:
        raise HTTPException(401, "E-posta ya da şifre hatalı")
    return r.json()["access_token"]


async def get_current_user(token: str | None = Depends(oauth2)):
    if not token:
        raise HTTPException(401, "Giriş gerekli")
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