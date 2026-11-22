"""Backend REST API'sine ince istemci.

Kullanıcının token'ı olduğu gibi iletilir. Yetki (RLS, rol ve fakülte filtresi) backend'de
uygulanmaya devam eder, burada kopyalanmaz. Token sunucuda saklanmaz; doğrulama önbelleğinde
yalnızca SHA-256 özeti tutulur.
"""
import hashlib
import time

import httpx
from fastmcp.server.dependencies import get_http_headers

from . import config


class HataKodu(Exception):
    """Araçlara döndürülecek, kullanıcıya gösterilebilir hata."""

    def __init__(self, kod: str, mesaj: str):
        super().__init__(mesaj)
        self.kod = kod
        self.mesaj = mesaj

    def govde(self) -> dict:
        return {"hata": True, "hata_kodu": self.kod, "mesaj": self.mesaj}


# Testlerde httpx.MockTransport verilir.
_transport: httpx.AsyncBaseTransport | None = None
_dogrulanan: dict[str, float] = {}  # token özeti -> geçerlilik bitişi (monotonic)


def _istemci() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=config.BACKEND_TIMEOUT_SN, transport=_transport)


def _auth_basligi() -> str:
    auth = get_http_headers(include_all=True).get("authorization", "")
    if not auth.lower().startswith("bearer ") or len(auth) < 15:
        raise HataKodu("KIMLIK_GEREKLI", "Oturum bilgisi bulunamadı. Lütfen tekrar giriş yapın.")
    return auth


def _hataya_cevir(durum: int) -> HataKodu | None:
    if durum < 400:
        return None
    tablo = {
        401: ("TOKEN_GECERSIZ", "Oturumun süresi dolmuş olabilir. Lütfen tekrar giriş yapın."),
        403: ("YETKI_YOK", "Bu bilgiye erişim yetkin yok."),
        404: ("KAYIT_BULUNAMADI", "İstenen kayıt bulunamadı."),
        422: ("PARAMETRE_GECERSIZ", "Gönderilen değerler geçersiz."),
        429: ("ORAN_SINIRI", "Çok fazla istek yapıldı. Biraz bekleyin."),
    }
    kod, mesaj = tablo.get(durum, ("GECICI_HATA", "Servis geçici olarak hata verdi."))
    return HataKodu(kod, mesaj)


async def _istek(yol: str, auth: str, params: dict | None = None) -> httpx.Response:
    try:
        async with _istemci() as istemci:
            return await istemci.get(
                f"{config.BACKEND_URL}{yol}", params=params, headers={"Authorization": auth}
            )
    except httpx.TimeoutException:
        raise HataKodu("ZAMAN_ASIMI", "Servis zamanında yanıt vermedi. Biraz sonra tekrar deneyin.")
    except httpx.HTTPError:
        raise HataKodu("GECICI_HATA", "Servise şu an ulaşılamıyor. Biraz sonra tekrar deneyin.")


async def backend_get(yol: str, params: dict | None = None) -> dict | list:
    yanit = await _istek(yol, _auth_basligi(), params)
    hata = _hataya_cevir(yanit.status_code)
    if hata:
        raise hata
    return yanit.json()


async def token_dogrula(auth: str) -> None:
    """Authorization başlığındaki token'ı backend'e doğrulatır (GET /me), sonucu kısa süre önbellekler.
    Geçersizse HataKodu('TOKEN_GECERSIZ') fırlatır."""
    anahtar = hashlib.sha256(auth.encode()).hexdigest()
    simdi = time.monotonic()
    if _dogrulanan.get(anahtar, 0) > simdi:
        return
    yanit = await _istek("/me", auth)
    hata = _hataya_cevir(yanit.status_code)
    if hata:
        raise hata
    if len(_dogrulanan) > 1000:
        for k in [k for k, bitis in _dogrulanan.items() if bitis <= simdi]:
            del _dogrulanan[k]
    _dogrulanan[anahtar] = simdi + config.TOKEN_ONBELLEK_SN
