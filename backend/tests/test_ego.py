import httpx
import pytest

from app.ego import EgoClient, EgoError, parse_minutes, parse_table

ORNEK = [
    {"arac_no": "-", "sure": "Sonraki Hareket Saati İlk Duraktan\n16:55 / 6 dk Sonra", "detay": "",
     "hat_no": "101", "hat_ad": "GÖLBAŞI-HAYMANA YOLU-BAHÇELİEVLER"},
    {"arac_no": "-", "sure": "Hattın Bugün İçin Başka Servisi Yok", "detay": "",
     "hat_no": "101-1", "hat_ad": "X"},
    {"arac_no": "12-129", "sure": "2 dk", "detay": "Körüklü‚ Engelli", "hat_no": "115-4", "hat_ad": "Y"},
    {"arac_no": "08-122", "sure": "8 dk", "detay": "Solo", "hat_no": "114-1", "hat_ad": "Z"},
]


def test_parse_minutes():
    assert parse_minutes("8 dk") == 8
    assert parse_minutes("1 sa 5 dk") == 65
    assert parse_minutes("Geliyor") == 0
    assert parse_minutes("geliyor") == 0
    assert parse_minutes("Yaklaşıyor") is None
    assert parse_minutes("") is None


def test_geliyor_dakika_sifir_ve_en_basta():
    rows = ORNEK + [{"arac_no": "01-001", "sure": "Geliyor", "detay": "", "hat_no": "1", "hat_ad": "A"}]
    canli, _ = parse_table(rows)
    assert canli[0]["arac_no"] == "01-001"
    assert canli[0]["dakika"] == 0 and canli[0]["geliyor"] is True
    assert canli[1]["geliyor"] is False


def test_parse_table_ayirir_ve_siralar():
    canli, tarife = parse_table(ORNEK)
    assert [c["arac_no"] for c in canli] == ["12-129", "08-122"]
    assert len(tarife) == 2
    assert tarife[0]["saat"] == "16:55"
    assert tarife[1]["saat"] is None


def make_client(handler, ttl=30):
    return EgoClient(ttl=ttl, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.mark.asyncio
async def test_cache_ikinci_istegi_ego_ya_gondermez():
    sayac = {"n": 0}

    def handler(req):
        sayac["n"] += 1
        return httpx.Response(200, json={"table": ORNEK, "message": "", "status": "TRUE"})

    c = make_client(handler)
    a = await c.arrivals("12579")
    b = await c.arrivals("12579")
    assert sayac["n"] == 1 and not a["stale"] and not b["stale"]


@pytest.mark.asyncio
async def test_hata_olursa_eski_veri_stale_doner():
    durum = {"ok": True}

    def handler(req):
        if durum["ok"]:
            return httpx.Response(200, json={"table": ORNEK, "status": "TRUE"})
        return httpx.Response(500)

    c = make_client(handler, ttl=0)  # her çağrıda yeniden sorgula
    await c.arrivals("12579")
    durum["ok"] = False
    r = await c.arrivals("12579")
    assert r["stale"] is True and len(r["canli"]) == 2


@pytest.mark.asyncio
async def test_hata_ve_onbellek_yoksa_EgoError():
    c = make_client(lambda req: httpx.Response(500))
    with pytest.raises(EgoError):
        await c.arrivals("99999")


@pytest.mark.asyncio
async def test_bos_tablo_bos_isaretlenir():
    c = make_client(lambda req: httpx.Response(200, json={"table": [], "status": "TRUE"}))
    r = await c.arrivals("10000")
    assert r["bos"] is True and r["canli"] == []