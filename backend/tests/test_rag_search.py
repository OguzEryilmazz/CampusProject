import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth, main
from app.db import Db
from app.rag.search import search


class FakeDb:
    def __init__(self, rows=None):
        self.rows, self.cagri = rows or [], []

    async def match_chunks(self, emb, k, rol, fakulte):
        self.cagri.append((emb, k, rol, fakulte))
        return self.rows

    async def user_scope(self, uid):
        return ("akademisyen", "Mühendislik")


class FakeEmb:
    model_id = "fake:v1"
    kinds = []

    async def embed(self, texts, kind="document"):
        FakeEmb.kinds.append(kind)
        return [[1.0, 0.0] for _ in texts]


ROW = {"icerik": "Yönetmelik – Madde 2\nmetin", "baslik": "Yönetmelik", "madde": "Madde 2",
       "kaynak_url": "https://x.edu.tr/y", "score": 0.83214}


async def test_arama_rol_ve_fakulteyi_veritabanina_iletir():
    db = FakeDb([ROW])
    sonuc = await search(db, FakeEmb(), " mazeret sınavı ", "akademisyen", "Mühendislik", k=3)
    assert db.cagri == [([1.0, 0.0], 3, "akademisyen", "Mühendislik")]
    assert FakeEmb.kinds[-1] == "query"          # arama metni sorgu olarak vektörlenir
    assert sonuc == [{"icerik": ROW["icerik"], "baslik": "Yönetmelik", "madde": "Madde 2",
                      "kaynak_url": "https://x.edu.tr/y", "score": 0.8321}]


async def test_bos_sorgu_aramaz():
    db = FakeDb([ROW])
    assert await search(db, FakeEmb(), "   ", "ogrenci", None) == []
    assert db.cagri == []


async def test_match_chunks_rpc_istegi():
    istek = {}

    def handler(req):
        import json
        istek["url"], istek["body"] = str(req.url), json.loads(req.content)
        return httpx.Response(200, json=[ROW])

    db = Db("https://x.supabase.co", "k", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await db.match_chunks([0.5, 0.25], 4, "ogrenci", None)
    assert istek["url"] == "https://x.supabase.co/rest/v1/rpc/match_chunks"
    assert istek["body"] == {"query_embedding": "[0.500000,0.250000]", "match_count": 4,
                             "p_rol": "ogrenci", "p_fakulte": None}


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
    db = FakeDb([ROW])
    monkeypatch.setitem(main.state, "db", db)
    monkeypatch.setitem(main.state, "embedder", FakeEmb())
    c = TestClient(main.app)
    c.db = db
    return c


H = {"Authorization": "Bearer gecerli"}


def test_endpoint_girissiz_401(client):
    assert client.get("/rag/search", params={"q": "mazeret"}).status_code == 401


def test_endpoint_rol_ve_fakulteyi_profilden_alir_istemciden_degil(client):
    r = client.get("/rag/search", params={"q": "mazeret", "rol": "idari", "fakulte": "Hukuk"}, headers=H)
    assert r.status_code == 200 and r.json()["sonuclar"][0]["madde"] == "Madde 2"
    assert client.db.cagri[0][2:] == ("akademisyen", "Mühendislik")   # sorgudaki sahte rol yok sayıldı


def test_endpoint_dogrulama(client):
    assert client.get("/rag/search", params={"q": "a"}, headers=H).status_code == 422
    assert client.get("/rag/search", params={"q": "mazeret", "k": 50}, headers=H).status_code == 422


def test_embedder_yoksa_503(client, monkeypatch):
    monkeypatch.setitem(main.state, "embedder", None)
    assert client.get("/rag/search", params={"q": "mazeret"}, headers=H).status_code == 503