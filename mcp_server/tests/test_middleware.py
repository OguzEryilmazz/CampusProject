import httpx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from kampus_mcp.auth_middleware import KimlikZorunlu


def uygulama():
    async def ok(request):
        return PlainTextResponse("ok")

    return KimlikZorunlu(Starlette(routes=[Route("/mcp", ok, methods=["POST"]), Route("/health", ok)]))


def backend(tablo):
    """Authorization -> durum kodu."""
    def handler(request):
        return httpx.Response(tablo.get(request.headers.get("authorization"), 401), json={})
    return handler


def test_matris(sahte_backend):
    sahte_backend(backend({"Bearer gecerli-token-123456": 200}))
    c = TestClient(uygulama())
    assert c.post("/mcp").status_code == 401                                              # başlık yok
    assert c.post("/mcp", headers={"Authorization": "Basic abc"}).status_code == 401      # şema yanlış
    r = c.post("/mcp", headers={"Authorization": "Bearer bozuk-token-123456"})
    assert r.status_code == 401 and r.json()["hata_kodu"] == "TOKEN_GECERSIZ"
    assert c.post("/mcp", headers={"Authorization": "Bearer gecerli-token-123456"}).status_code == 200
    assert c.get("/health").status_code == 200                                            # sağlık açık


def test_backend_403_yetki_yok(sahte_backend):
    sahte_backend(backend({"Bearer x-token-123456789": 403}))
    r = TestClient(uygulama()).post("/mcp", headers={"Authorization": "Bearer x-token-123456789"})
    assert r.status_code == 403 and r.json()["hata_kodu"] == "YETKI_YOK"


def test_backend_kapaliysa_503(sahte_backend):
    def kopuk(request):
        raise httpx.ConnectError("x")
    sahte_backend(kopuk)
    r = TestClient(uygulama()).post("/mcp", headers={"Authorization": "Bearer gecerli-token-123456"})
    assert r.status_code == 503 and r.json()["hata_kodu"] == "GECICI_HATA"


def test_dogrulama_onbellege_alinir_gecersiz_alinmaz(sahte_backend):
    istekler = sahte_backend(backend({"Bearer gecerli-token-123456": 200}))
    c = TestClient(uygulama())
    h = {"Authorization": "Bearer gecerli-token-123456"}
    c.post("/mcp", headers=h); c.post("/mcp", headers=h); c.post("/mcp", headers=h)
    assert len(istekler) == 1
    kotu = {"Authorization": "Bearer bozuk-token-123456"}
    c.post("/mcp", headers=kotu); c.post("/mcp", headers=kotu)
    assert len(istekler) == 3  # geçersiz token her seferinde yeniden sorulur


def test_profili_olmayan_ama_gecerli_token_gecer(sahte_backend):
    # /me 404 = token geçerli, profil satırı yok. 503 değil, istek içeri alınmalı.
    sahte_backend(backend({"Bearer profilsiz-token-12345": 404}))
    r = TestClient(uygulama()).post("/mcp", headers={"Authorization": "Bearer profilsiz-token-12345"})
    assert r.status_code == 200
