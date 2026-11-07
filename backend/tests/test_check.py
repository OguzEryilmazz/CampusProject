from datetime import datetime
from zoneinfo import ZoneInfo

from app.ego import EgoError
from app.scheduler import run_check

TZ = ZoneInfo("Europe/Istanbul")
NOW = datetime(2026, 11, 4, 8, 20, tzinfo=TZ)  # Çarşamba, ders 09:00 -> pencere içinde


class FakeDb:
    def __init__(self, items, stops, recent=(), kampus="Gölbaşı", hatlar=None):
        self.items, self.stops, self.recent = items, stops, set(recent)
        self.kampus = kampus
        self.hatlar = {"Gölbaşı": {"114-1"}} if hatlar is None else hatlar
        self.inserted = []

    async def schedule_today(self, gun):
        assert gun == 3  # Çarşamba
        return self.items

    async def favorite_stops(self, ids):
        return [s for s in self.stops if s["user_id"] in ids]

    async def profile_campuses(self, ids):
        return {i: self.kampus for i in ids}

    async def campus_lines(self, campuses):
        return {k: v for k, v in self.hatlar.items() if k in campuses}

    async def recent_notifications(self, ids, since):
        return self.recent

    async def insert_notification(self, n):
        self.inserted.append(n)


class FakeEgo:
    def __init__(self, canli=None, hata=False, stale=False):
        self.canli, self.hata, self.stale, self.cagri = canli or [], hata, stale, 0

    async def arrivals(self, durak):
        self.cagri += 1
        if self.hata:
            raise EgoError("x")
        return {"canli": self.canli, "stale": self.stale}


ITEMS = [{"user_id": "u1", "baslangic": "09:00:00", "bitis": "10:50:00"},
         {"user_id": "u1", "baslangic": "13:00:00", "bitis": "14:50:00"}]
STOP = {"user_id": "u1", "durak_no": "12579", "ad": "Ev durağı"}
BUS = {"hat_no": "114-1", "dakika": 9, "arac_no": "12-133", "geliyor": False}


async def test_pencere_icinde_bildirim_uretir():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo([BUS])
    sonuc = await run_check(db, ego, NOW)
    assert len(sonuc) == 1 == len(db.inserted)
    n = db.inserted[0]
    assert n["user_id"] == "u1" and n["arac_no"] == "12-133" and n["dakika"] == 9
    assert "09:00" in n["mesaj"] and "9 dk" in n["mesaj"]


async def test_pencere_disinda_ego_ya_gitmez():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo([BUS])
    gec = datetime(2026, 11, 4, 7, 30, tzinfo=TZ)  # ders 09:00, pencere 08:00'de başlar
    assert await run_check(db, ego, gec) == []
    assert ego.cagri == 0


async def test_kampus_hat_listesi_bossa_bildirim_yok():
    db, ego = FakeDb(ITEMS, [STOP], hatlar={}), FakeEgo([BUS])
    assert await run_check(db, ego, NOW) == []
    assert ego.cagri == 0


async def test_kampusu_olmayan_kullaniciya_bildirim_yok():
    db, ego = FakeDb(ITEMS, [STOP], kampus=None), FakeEgo([BUS])
    assert await run_check(db, ego, NOW) == []
    assert ego.cagri == 0


async def test_kampus_disi_hat_filtrelenir():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo([{**BUS, "hat_no": "101", "dakika": 3}])
    assert await run_check(db, ego, NOW) == []  # 101 Gölbaşı listesinde yok


async def test_yakinda_bildirim_varsa_tekrar_yok():
    db, ego = FakeDb(ITEMS, [STOP], recent={("u1", "12579")}), FakeEgo([BUS])
    assert await run_check(db, ego, NOW) == []


async def test_ego_hatasinda_sessizce_atlar():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo(hata=True)
    assert await run_check(db, ego, NOW) == []


async def test_uygun_arac_yoksa_bildirim_yok():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo([{**BUS, "dakika": 25}])
    assert await run_check(db, ego, NOW) == []