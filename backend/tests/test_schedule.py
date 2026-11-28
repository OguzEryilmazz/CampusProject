"""/me/schedule ucu ve Db.schedule_of testleri. Gerçek servislere bağlanmaz."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import Db
from app.main import app, state

UID = "11111111-1111-1111-1111-111111111111"
SATIRLAR = [
    {"id": 1, "gun": 1, "baslangic": "09:00:00", "bitis": "10:50:00", "baslik": "Algoritma", "yer": "B-204"},
    {"id": 2, "gun": 3, "baslangic": "13:00:00", "bitis": "14:50:00", "baslik": "Ağlar", "yer": None},
]


class SahteDb:
    def __init__(self):
        self.cagrilar = []

    async def schedule_of(self, user_id, gun=None):
        self.cagrilar.append((user_id, gun))
        return [s for s in SATIRLAR if gun is None or s["gun"] == gun]


@pytest.fixture
def istemci():
    onceki_db = state["db"]
    sahte = SahteDb()
    state["db"] = sahte
    app.dependency_overrides[get_current_user] = lambda: {"id": UID, "email": None}
    yield TestClient(app), sahte   # `with` kullanılmadığı için lifespan (zamanlayıcı) çalışmaz
    app.dependency_overrides.pop(get_current_user, None)
    state["db"] = onceki_db


def test_tum_hafta_doner(istemci):
    c, sahte = istemci
    r = c.get("/me/schedule")
    assert r.status_code == 200 and [s["baslik"] for s in r.json()] == ["Algoritma", "Ağlar"]
    assert r.json()[1]["yer"] is None
    assert sahte.cagrilar == [(UID, None)]


def test_gun_filtresi_iletilir(istemci):
    c, sahte = istemci
    r = c.get("/me/schedule", params={"gun": 3})
    assert [s["id"] for s in r.json()] == [2] and sahte.cagrilar == [(UID, 3)]


def test_kullanici_kimligi_yalniz_tokendan_gelir(istemci):
    c, sahte = istemci
    c.get("/me/schedule", params={"user_id": "baska-kullanici"})
    assert sahte.cagrilar == [(UID, None)]


@pytest.mark.parametrize("gun", [0, 8, -1])
def test_gecersiz_gun_422(istemci, gun):
    c, sahte = istemci
    assert c.get("/me/schedule", params={"gun": gun}).status_code == 422
    assert sahte.cagrilar == []


def test_girissiz_401():
    app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(app).get("/me/schedule").status_code == 401


def test_db_sorgusu_user_id_ile_sinirlanir_ve_siralanir():
    istekler = []

    def handler(request: httpx.Request):
        istekler.append(request)
        return httpx.Response(200, json=SATIRLAR)

    db = Db("http://sb.test", "anahtar", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    asyncio.run(db.schedule_of(UID, 1))
    p = dict(istekler[0].url.params)
    assert istekler[0].url.path == "/rest/v1/schedule_items"
    assert p["user_id"] == f"eq.{UID}" and p["gun"] == "eq.1" and p["order"] == "gun.asc,baslangic.asc"
    asyncio.run(db.schedule_of(UID))
    assert "gun" not in dict(istekler[1].url.params)
