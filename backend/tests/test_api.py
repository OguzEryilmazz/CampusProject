import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth, main
from app.ego import EgoError


def arac(hat, dk, no):
    return {"hat_no": hat, "hat_ad": "X", "arac_no": no, "dakika": dk, "geliyor": dk == 0,
            "sure_ham": f"{dk} dk", "detay": ""}


class FakeDb:
    def __init__(self, hatlar=None, prof="var"):
        self.hatlar = {"Gölbaşı": {"114-1"}} if hatlar is None else hatlar
        self.prof = {"ad": "Test", "rol": "ogrenci", "fakulte": "Mühendislik", "kampus": "Gölbaşı",
                     "bildirim_acik": True} if prof == "var" else None
        self.limit = None

    async def profile_of(self, uid):
        return self.prof

    async def favorite_stops_of(self, uid):
        return [{"id": 1, "durak_no": "12579", "ad": "Ev", "bildirim_dk": 10},
                {"id": 2, "durak_no": "11002", "ad": "Okul", "bildirim_dk": 15}]

    async def campus_lines(self, campuses):
        return {k: v for k, v in self.hatlar.items() if k in campuses}

    async def notifications_of(self, uid, limit=20):
        self.limit = limit
        return [{"id": 7, "durak_no": "12579", "mesaj": "m", "dakika": 5, "araclar": [{"arac_no": "A"}],
                 "created_at": "2026-11-14T08:00:00+00:00", "sent_at": None}]


class FakeEgo:
    def __init__(self):
        self.veri = {"12579": [arac("114-1", 5, "A"), arac("101", 3, "B")]}

    async def arrivals(self, durak):
        if durak == "11002":
            raise EgoError("x")
        return {"durak": durak, "canli": self.veri[durak], "tarife": [], "bos": False, "stale": False}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "k")
    auth._CACHE.clear()
    gorulen = {}

    def handler(req):
        if req.url.path.endswith("/auth/v1/token"):
            import json
            gorulen["login"] = json.loads(req.content)
            gorulen["grant"] = req.url.params["grant_type"]
            if gorulen["login"]["password"] == "dogru":
                return httpx.Response(200, json={"access_token": "gecerli", "token_type": "bearer"})
            return httpx.Response(400, json={"msg": "Invalid login credentials"})
        if req.headers.get("authorization") == "Bearer gecerli":
            return httpx.Response(200, json={"id": "u1", "email": "a@b.c"})
        return httpx.Response(401, json={})

    monkeypatch.setattr(auth, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(main, "ego", FakeEgo())
    for k, v in {"db": FakeDb(), "push": None, "embedder": None, "scheduler": False}.items():
        monkeypatch.setitem(main.state, k, v)
    c = TestClient(main.app)
    c.gorulen = gorulen
    return c


H = {"Authorization": "Bearer gecerli"}


def test_health_girissiz_ve_ozellikleri_gosterir(client, monkeypatch):
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["durum"] == "ok" and j["surum"] == main.VERSION
    assert j["ozellikler"] == {"veritabani": True, "zamanlayici": False, "push": False, "rag": False}
    assert "key" not in str(j).lower() and "anahtar" not in str(j).lower()


def test_openapi_dokumantasyonu_tum_uc_noktalari_aciklar(client):
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    for yol in ("/health", "/config", "/auth/token", "/me", "/me/stops", "/me/notifications",
                "/stops/{durak_no}/arrivals", "/devices", "/devices/{token}", "/rag/search"):
        assert yol in paths, yol
        for method, op in paths[yol].items():
            assert op.get("summary") and op.get("tags"), (yol, method)   # her uç nokta açıklamalı ve etiketli
    assert "/" not in paths                                              # test sayfası dokümanda yok
    assert spec["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == "auth/token"
    assert client.get("/docs").status_code == 200


def test_swagger_giris_dogru_sifre_token_doner(client):
    r = client.post("/auth/token", data={"username": "a@b.c", "password": "dogru"})
    assert r.status_code == 200 and r.json() == {"access_token": "gecerli", "token_type": "bearer"}
    assert client.gorulen["login"] == {"email": "a@b.c", "password": "dogru"}
    assert client.gorulen["grant"] == "password"


def test_yanlis_sifre_401(client):
    assert client.post("/auth/token", data={"username": "a@b.c", "password": "yanlis"}).status_code == 401


def test_me_profil_ve_yetki(client):
    assert client.get("/me").status_code == 401
    r = client.get("/me", headers=H)
    assert r.status_code == 200 and r.json()["kampus"] == "Gölbaşı" and r.json()["rol"] == "ogrenci"


def test_me_profil_yoksa_404(client, monkeypatch):
    monkeypatch.setitem(main.state, "db", FakeDb(prof=None))
    assert client.get("/me", headers=H).status_code == 404


def test_me_stops_kampus_hatlarina_gore_filtreler_ve_ego_hatasini_isaretler(client):
    r = client.get("/me/stops", headers=H)
    assert r.status_code == 200
    ev, okul = r.json()
    assert [v["hat_no"] for v in ev["canli"]] == ["114-1"]          # 101 kampüs hattı değil, elendi
    assert ev["filtre_aktif"] is True and ev["veri_alinamadi"] is False and ev["bildirim_dk"] == 10
    assert okul["veri_alinamadi"] is True and okul["canli"] == []   # EGO hatası diğer durağı bozmaz


def test_me_stops_hat_listesi_tanimsizsa_hepsini_gosterir(client, monkeypatch):
    monkeypatch.setitem(main.state, "db", FakeDb(hatlar={}))
    ev = client.get("/me/stops", headers=H).json()[0]
    assert {v["hat_no"] for v in ev["canli"]} == {"114-1", "101"} and ev["filtre_aktif"] is False


def test_me_notifications_limit(client):
    r = client.get("/me/notifications", params={"limit": 5}, headers=H)
    assert r.status_code == 200 and r.json()[0]["mesaj"] == "m" and r.json()[0]["sent_at"] is None
    assert main.state["db"].limit == 5
    assert client.get("/me/notifications", params={"limit": 0}, headers=H).status_code == 422
    assert client.get("/me/notifications", params={"limit": 101}, headers=H).status_code == 422


def test_ham_arrivals_modelle_uyumlu(client):
    r = client.get("/stops/12579/arrivals", headers=H)
    assert r.status_code == 200 and len(r.json()["canli"]) == 2 and r.json()["stale"] is False
