"""/mcp için kimlik kontrolü (rehber 5.5 ve 9).

- Bearer yok            -> 401 KIMLIK_GEREKLI
- Token geçersiz        -> 401 TOKEN_GECERSIZ (backend doğrular, burada imza çözülmez)
- Backend'e ulaşılamadı -> 503 GECICI_HATA
"""
from starlette.responses import JSONResponse

from . import backend_client
from .backend_client import HataKodu

ACIK_YOLLAR = {"/health"}
_DURUM = {"KIMLIK_GEREKLI": 401, "TOKEN_GECERSIZ": 401, "YETKI_YOK": 403,
          "ORAN_SINIRI": 429}


class KimlikZorunlu:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] not in ACIK_YOLLAR:
            basliklar = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            auth = basliklar.get("authorization", "")
            try:
                if not auth.lower().startswith("bearer "):
                    raise HataKodu("KIMLIK_GEREKLI", "Kimlik bilgisi gerekli.")
                await backend_client.token_dogrula(auth)
            except HataKodu as e:
                durum = _DURUM.get(e.kod, 503)
                basliklar_cikis = {"WWW-Authenticate": "Bearer"} if durum == 401 else None
                yanit = JSONResponse(e.govde(), status_code=durum, headers=basliklar_cikis)
                await yanit(scope, receive, send)
                return
        await self.app(scope, receive, send)
