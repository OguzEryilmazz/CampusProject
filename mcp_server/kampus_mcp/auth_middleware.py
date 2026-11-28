"""/mcp için kimlik kontrolü ve oran sınırı (rehber 5.5, 9, 10).

- Bearer yok                 -> 401 KIMLIK_GEREKLI
- Token geçersiz             -> 401 TOKEN_GECERSIZ (backend doğrular, burada imza çözülmez)
- Backend'e ulaşılamadı      -> 503 GECICI_HATA
- Aynı IP'den çok başarısız deneme -> 429 ORAN_SINIRI (backend'e hiç sorulmaz)
- Aynı token'dan çok istek   -> 429 ORAN_SINIRI
"""
import hashlib

from starlette.responses import JSONResponse

from . import backend_client, config
from .backend_client import HataKodu
from .oran_siniri import SabitPencere

ACIK_YOLLAR = {"/health"}
_DURUM = {"KIMLIK_GEREKLI": 401, "TOKEN_GECERSIZ": 401, "YETKI_YOK": 403, "ORAN_SINIRI": 429}

istekler = SabitPencere(60)   # anahtar: token özeti
hatalar = SabitPencere(60)    # anahtar: istemci IP'si (başarısız kimlik denemeleri)


def _ip(scope, basliklar: dict) -> str:
    if config.GUVEN_VEKIL:
        xff = basliklar.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    istemci = scope.get("client")
    return istemci[0] if istemci else "bilinmiyor"


async def _yanit(scope, receive, send, e: HataKodu, durum: int, ek: dict | None = None):
    basliklar = dict(ek or {})
    if durum == 401:
        basliklar["WWW-Authenticate"] = "Bearer"
    await JSONResponse(e.govde(), status_code=durum, headers=basliklar or None)(scope, receive, send)


class KimlikZorunlu:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in ACIK_YOLLAR:
            await self.app(scope, receive, send)
            return

        basliklar = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        auth = basliklar.get("authorization", "")
        ip = _ip(scope, basliklar)

        # Çok sayıda başarısız deneme yapan IP'nin isteği backend'e doğrulatılmadan kesilir.
        if hatalar.sayac(ip) >= config.HATA_LIMITI_DK:
            e = HataKodu("ORAN_SINIRI", "Çok fazla başarısız deneme. Biraz bekleyin.")
            await _yanit(scope, receive, send, e, 429, {"Retry-After": str(hatalar.kalan_sn(ip))})
            return

        try:
            if not auth.lower().startswith("bearer "):
                raise HataKodu("KIMLIK_GEREKLI", "Kimlik bilgisi gerekli.")
            await backend_client.token_dogrula(auth)
        except HataKodu as e:
            if e.kod in ("KIMLIK_GEREKLI", "TOKEN_GECERSIZ"):
                hatalar.say(ip)
            await _yanit(scope, receive, send, e, _DURUM.get(e.kod, 503))
            return

        anahtar = hashlib.sha256(auth.encode()).hexdigest()[:16]
        if istekler.say(anahtar) > config.ISTEK_LIMITI_DK:
            e = HataKodu("ORAN_SINIRI", "Çok fazla istek yapıldı. Biraz bekleyin.")
            await _yanit(scope, receive, send, e, 429, {"Retry-After": str(istekler.kalan_sn(anahtar))})
            return

        await self.app(scope, receive, send)
