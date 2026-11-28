"""Araç iş mantığı: backend çağrısı + yanıt şekillendirme. MCP kaydı server.py'dedir."""
from datetime import datetime

from . import config, shapers
from .backend_client import HataKodu, backend_get


async def _guvenli(is_):
    try:
        return await is_()
    except HataKodu as e:
        return e.govde()


async def profilim_getir() -> dict:
    return await _guvenli(lambda: _profil())


async def _profil():
    return shapers.profil(await backend_get("/me"))


async def favori_duraklarim_getir() -> dict:
    async def is_():
        return shapers.favori_duraklar(await backend_get("/me/stops"))
    return await _guvenli(is_)


async def durak_yaklasan_araclar(durak_no: str) -> dict:
    async def is_():
        return shapers.durak_yaklasan(durak_no, await backend_get(f"/stops/{durak_no}/arrivals"))
    return await _guvenli(is_)


async def bildirimlerim_getir(limit: int = 5) -> dict:
    async def is_():
        return shapers.bildirimler(await backend_get("/me/notifications"), limit)
    return await _guvenli(is_)


async def dokuman_ara(sorgu: str, limit: int = 5) -> dict:
    async def is_():
        # Rol ve fakülte filtresi backend'de profilden uygulanır, buradan parametre gitmez.
        return shapers.arama(await backend_get("/rag/search", {"q": sorgu}), limit)
    return await _guvenli(is_)


async def ders_programim_getir(kapsam: str = "bugun", simdi: datetime | None = None) -> dict:
    async def is_():
        now = simdi or datetime.now(config.TZ)
        params = None
        if kapsam in ("bugun", "yarin"):
            params = {"gun": shapers.hedef_gun(kapsam, now)[0]}
        return shapers.ders_programi(await backend_get("/me/schedule", params), kapsam, now)
    return await _guvenli(is_)
