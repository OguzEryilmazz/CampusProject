import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth, main


class FakeEgo:
    async def arrivals(self, durak):
        return {"durak": durak, "canli": [], "tarife": [], "bos": True, "stale": False}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co/rest/v1/")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anahtar")
    auth._CACHE.clear()
    calls = {"n": 0, "url": None}

    def handler(req):
        calls["n"] += 1
        calls["url"] = str(req.url)
        if req.headers.get("authorization") == "Bearer gecerli":
            return httpx.Response(200, json={"id": "u1", "email": "a@b.c"})
        return httpx.Response(401, json={"msg": "bad"})

    monkeypatch.setattr(auth, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(main, "ego", FakeEgo())
    c = TestClient(main.app)
    c.calls = calls
    return c


def test_token_yoksa_401(client):
    assert client.get("/stops/12579/arrivals").status_code == 401


def test_gecersiz_token_401(client):
    r = client.get("/stops/12579/arrivals", headers={"Authorization": "Bearer kotu"})
    assert r.status_code == 401


def test_gecerli_token_200_ve_kok_adres_kullanilir(client):
    r = client.get("/stops/12579/arrivals", headers={"Authorization": "Bearer gecerli"})
    assert r.status_code == 200 and r.json()["durak"] == "12579"
    assert client.calls["url"] == "https://x.supabase.co/auth/v1/user"


def test_dogrulama_onbellege_alinir(client):
    h = {"Authorization": "Bearer gecerli"}
    client.get("/stops/12579/arrivals", headers=h)
    client.get("/stops/10000/arrivals", headers=h)
    assert client.calls["n"] == 1


def test_gecersiz_durak_numarasi_422(client):
    r = client.get("/stops/abc/arrivals", headers={"Authorization": "Bearer gecerli"})
    assert r.status_code == 422


def test_config_ve_sayfa_giris_istemez(client):
    assert client.get("/config").json()["supabase_url"] == "https://x.supabase.co"
    assert client.get("/").status_code == 200