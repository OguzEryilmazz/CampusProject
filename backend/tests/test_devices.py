import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth, main


class FakeDb:
    def __init__(self):
        self.kayit, self.silinen = [], []

    async def upsert_device(self, uid, token, platform):
        self.kayit.append((uid, token, platform))

    async def delete_device(self, token, user_id=None):
        self.silinen.append((token, user_id))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "k")
    auth._CACHE.clear()

    def handler(req):
        if req.headers.get("authorization") == "Bearer gecerli":
            return httpx.Response(200, json={"id": "u1", "email": "a@b.c"})
        return httpx.Response(401, json={})

    monkeypatch.setattr(auth, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    db = FakeDb()
    monkeypatch.setitem(main.state, "db", db)
    c = TestClient(main.app)
    c.db = db
    return c


H = {"Authorization": "Bearer gecerli"}
TOKEN = "fcm-token-" + "x" * 30


def test_cihaz_kaydi_girissiz_401(client):
    assert client.post("/devices", json={"token": TOKEN}).status_code == 401


def test_cihaz_kaydi_kullanici_kimligiyle_yapilir(client):
    r = client.post("/devices", json={"token": TOKEN, "platform": "android"}, headers=H)
    assert r.status_code == 204
    assert client.db.kayit == [("u1", TOKEN, "android")]


def test_cihaz_kaydi_gecersiz_girdi_422(client):
    assert client.post("/devices", json={"token": "kisa"}, headers=H).status_code == 422
    assert client.post("/devices", json={"token": TOKEN, "platform": "web"}, headers=H).status_code == 422


def test_cihaz_silme_yalnizca_kendi_cihazi(client):
    assert client.delete(f"/devices/{TOKEN}", headers=H).status_code == 204
    assert client.db.silinen == [(TOKEN, "u1")]


def test_db_yoksa_503(client, monkeypatch):
    monkeypatch.setitem(main.state, "db", None)
    assert client.post("/devices", json={"token": TOKEN}, headers=H).status_code == 503