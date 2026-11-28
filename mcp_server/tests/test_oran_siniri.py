import httpx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from kampus_mcp import config
from kampus_mcp.auth_middleware import KimlikZorunlu
from kampus_mcp.oran_siniri import SabitPencere


class Saat:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_pencere_sayar_ve_sure_dolunca_sifirlanir():
    saat = Saat()
    p = SabitPencere(60, saat=saat)
    assert [p.say("a"), p.say("a"), p.say("b")] == [1, 2, 1]
    assert p.sayac("a") == 2 and p.sayac("yok") == 0
    saat.t += 61
    assert p.sayac("a") == 0 and p.say("a") == 1


def test_kalan_sure_en_az_bir_saniye():
    saat = Saat()
    p = SabitPencere(60, saat=saat)
    p.say("a")
    saat.t += 30
    assert 1 <= p.kalan_sn("a") <= 31


def test_cok_anahtar_olunca_eskiler_temizlenir():
    saat = Saat()
    p = SabitPencere(60, saat=saat, max_anahtar=3)
    for i in range(4):
        p.say(f"k{i}")
    saat.t += 100
    p.say("yeni")
    assert len(p._kayit) == 1


def uygulama():
    async def ok(request):
        return PlainTextResponse("ok")
    return KimlikZorunlu(Starlette(routes=[Route("/mcp", ok, methods=["POST"]), Route("/health", ok)]))


def backend_yalniz(gecerli):
    def handler(request):
        return httpx.Response(200 if request.headers.get("authorization") == gecerli else 401, json={})
    return handler


def test_token_basina_istek_siniri(sahte_backend, monkeypatch):
    monkeypatch.setattr(config, "ISTEK_LIMITI_DK", 3)
    sahte_backend(backend_yalniz("Bearer gecerli-token-123456"))
    c = TestClient(uygulama())
    h = {"Authorization": "Bearer gecerli-token-123456"}
    assert [c.post("/mcp", headers=h).status_code for _ in range(3)] == [200, 200, 200]
    r = c.post("/mcp", headers=h)
    assert r.status_code == 429 and r.json()["hata_kodu"] == "ORAN_SINIRI" and int(r.headers["retry-after"]) >= 1
    # başka bir token etkilenmez
    sahte_backend(backend_yalniz("Bearer baska-token-1234567"))
    assert c.post("/mcp", headers={"Authorization": "Bearer baska-token-1234567"}).status_code == 200


def test_cok_basarisiz_deneme_backende_sormadan_kesilir(sahte_backend, monkeypatch):
    monkeypatch.setattr(config, "HATA_LIMITI_DK", 3)
    istekler = sahte_backend(backend_yalniz("Bearer gecerli-token-123456"))
    c = TestClient(uygulama())
    kotu = {"Authorization": "Bearer bozuk-token-123456"}
    assert [c.post("/mcp", headers=kotu).status_code for _ in range(3)] == [401, 401, 401]
    sorgu_sayisi = len(istekler)
    r = c.post("/mcp", headers=kotu)
    assert r.status_code == 429 and len(istekler) == sorgu_sayisi  # backend'e gidilmedi
    # aynı IP'den gelen geçerli token da engellenir (IP başarısız deneme limitini aştı)
    assert c.post("/mcp", headers={"Authorization": "Bearer gecerli-token-123456"}).status_code == 429


def test_backend_hatasi_basarisiz_deneme_sayilmaz(sahte_backend, monkeypatch):
    monkeypatch.setattr(config, "HATA_LIMITI_DK", 2)

    def kopuk(request):
        raise httpx.ConnectError("x")
    sahte_backend(kopuk)
    c = TestClient(uygulama())
    h = {"Authorization": "Bearer gecerli-token-123456"}
    assert [c.post("/mcp", headers=h).status_code for _ in range(4)] == [503, 503, 503, 503]


def test_health_sinirdan_etkilenmez(sahte_backend, monkeypatch):
    monkeypatch.setattr(config, "HATA_LIMITI_DK", 1)
    sahte_backend(backend_yalniz("x"))
    c = TestClient(uygulama())
    c.post("/mcp")  # başlıksız: IP'nin hata sayacı dolar
    assert c.post("/mcp").status_code == 429
    assert c.get("/health").status_code == 200


def test_xff_yalniz_guvenilen_vekil_acikken_kullanilir(sahte_backend, monkeypatch):
    monkeypatch.setattr(config, "HATA_LIMITI_DK", 2)
    sahte_backend(backend_yalniz("x"))
    c = TestClient(uygulama())
    for _ in range(2):
        c.post("/mcp", headers={"X-Forwarded-For": "1.1.1.1"})
    # GUVEN_VEKIL kapalı: XFF yok sayılır, gerçek IP (testclient) sayılır -> limit doldu
    assert c.post("/mcp", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429
    from kampus_mcp import auth_middleware
    auth_middleware.hatalar.temizle()
    monkeypatch.setattr(config, "GUVEN_VEKIL", True)
    for _ in range(2):
        c.post("/mcp", headers={"X-Forwarded-For": "1.1.1.1"})
    assert c.post("/mcp", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 401  # farklı IP, sayaç ayrı
    assert c.post("/mcp", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
