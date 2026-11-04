"""EGO canlı otobüs servisi adapter'ı (resmi olmayan endpoint)."""
import asyncio
import re
import time

import httpx

URL = "https://egocptsrvand.ego.gov.tr/mblSrv14/service.asp"
HEADERS = {"User-Agent": "okul-bitirme-projesi/0.1"}
CACHE_TTL = 30  # saniye, durak başına paylaşılan önbellek


class EgoError(Exception):
    """EGO'dan geçerli cevap alınamadı."""


def parse_minutes(text):
    """'8 dk' -> 8, '1 sa 5 dk' -> 65, 'Geliyor' -> 0, tanınmayan biçim -> None."""
    if (text or "").strip().lower().rstrip(".!") == "geliyor":
        return 0
    m = re.fullmatch(r"\s*(?:(\d+)\s*sa)?\s*(?:(\d+)\s*dk)?\s*", text or "")
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def parse_table(rows):
    """Ham 'table' satırlarını canlı araç ve tarife satırlarına ayırır."""
    canli, tarife = [], []
    for r in rows:
        sure = (r.get("sure") or "").strip()
        base = {
            "hat_no": r.get("hat_no"),
            "hat_ad": r.get("hat_ad"),
        }
        if (r.get("arac_no") or "-") not in ("-", ""):
            canli.append({
                **base,
                "arac_no": r["arac_no"],
                "dakika": parse_minutes(sure),
                "geliyor": sure.strip().lower().rstrip(".!") == "geliyor",
                "sure_ham": sure,
                "detay": r.get("detay") or "",
            })
        else:
            saat = re.search(r"\b(\d{1,2}:\d{2})\b", sure)
            tarife.append({
                **base,
                "aciklama": sure.replace("\n", " "),
                "saat": saat.group(1) if saat else None,
            })
    canli.sort(key=lambda x: (x["dakika"] is None, x["dakika"]))
    return canli, tarife


class EgoClient:
    def __init__(self, ttl=CACHE_TTL, http=None):
        self._ttl = ttl
        self._http = http or httpx.AsyncClient(timeout=15, headers=HEADERS)
        self._cache = {}   # durak -> (monotonic, sonuç)
        self._locks = {}

    async def _fetch(self, durak):
        try:
            r = await self._http.get(URL, params={"FNC": "Otobusler", "DURAK": durak})
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise EgoError(str(e)) from e
        if str(data.get("status")).upper() != "TRUE":
            raise EgoError(f"EGO status: {data.get('status')}")
        canli, tarife = parse_table(data.get("table", []))
        return {
            "durak": durak,
            "canli": canli,
            "tarife": tarife,
            "bos": not data.get("table"),  # geçersiz numara ya da araç yok
            "alindi": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

    async def arrivals(self, durak):
        lock = self._locks.setdefault(durak, asyncio.Lock())
        async with lock:  # aynı durak için eşzamanlı istekler tek sorguya iner
            hit = self._cache.get(durak)
            if hit and time.monotonic() - hit[0] < self._ttl:
                return {**hit[1], "stale": False}
            try:
                result = await self._fetch(durak)
            except EgoError:
                if hit:  # son geçerli veriyi eski olduğunu belirterek ver
                    return {**hit[1], "stale": True}
                raise
            self._cache[durak] = (time.monotonic(), result)
            return {**result, "stale": False}