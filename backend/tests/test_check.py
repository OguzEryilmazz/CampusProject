from datetime import datetime
from zoneinfo import ZoneInfo

from app.ego import EgoError
from app.push import PushError
from app.scheduler import run_check

TZ = ZoneInfo("Europe/Istanbul")
NOW = datetime(2026, 11, 4, 8, 20, tzinfo=TZ)  # Çarşamba, ders 09:00 -> pencere içinde


class FakeDb:
    def __init__(self, items, stops, recent=None, kampus="Gölbaşı", hatlar=None, acik=True):
        self.items, self.stops = items, stops
        self.recent = recent or {}
        self.kampus, self.acik = kampus, acik
        self.hatlar = {"Gölbaşı": {"114-1", "115-1", "115-4"}} if hatlar is None else hatlar
        self.inserted = []
        self.tokens, self.silinen, self.gonderildi = [], [], []

    async def schedule_today(self, gun):
        assert gun == 3  # Çarşamba
        return self.items

    async def favorite_stops(self, ids):
        return [s for s in self.stops if s["user_id"] in ids]

    async def profiles(self, ids):
        return {i: {"kampus": self.kampus, "bildirim_acik": self.acik} for i in ids}

    async def campus_lines(self, campuses):
        return {k: v for k, v in self.hatlar.items() if k in campuses}

    async def recent_notifications(self, ids, since):
        return {k: set(v) for k, v in self.recent.items()}

    async def insert_notification(self, n):
        self.inserted.append(n)
        return len(self.inserted)

    async def tokens_of(self, uid):
        return list(self.tokens)

    async def delete_device(self, token, user_id=None):
        self.silinen.append(token)

    async def mark_sent(self, notif_id, when=None):
        self.gonderildi.append(notif_id)


class FakeEgo:
    def __init__(self, canli=None, hata=False, stale=False):
        self.canli, self.hata, self.stale, self.cagri = canli or [], hata, stale, 0

    async def arrivals(self, durak):
        self.cagri += 1
        if self.hata:
            raise EgoError("x")
        return {"canli": self.canli, "stale": self.stale}


class FakePush:
    def __init__(self, sonuclar=None, hata=False):
        self.sonuclar, self.hata, self.gonderilen = sonuclar or {}, hata, []

    async def send(self, token, title, body, data=None):
        if self.hata:
            raise PushError("fcm kapalı")
        self.gonderilen.append((token, title, body, data))
        return self.sonuclar.get(token, "ok")


ITEMS = [{"user_id": "u1", "baslangic": "09:00:00", "bitis": "10:50:00"},
         {"user_id": "u1", "baslangic": "13:00:00", "bitis": "14:50:00"}]
STOP = {"user_id": "u1", "durak_no": "12579", "ad": "Ev durağı", "bildirim_dk": 15}


def bus(hat, dk, no):
    return {"hat_no": hat, "dakika": dk, "arac_no": no, "geliyor": dk == 0}


async def test_tek_arac_icin_bildirim():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo([bus("114-1", 9, "A")])
    sonuc = await run_check(db, ego, NOW)
    assert len(sonuc) == 1 == len(db.inserted)
    n = db.inserted[0]
    assert n["arac_no"] == "A" and n["dakika"] == 9 and len(n["araclar"]) == 1
    assert "09:00" in n["mesaj"] and "9 dk" in n["mesaj"]


async def test_esik_kadar_dakika_icindeki_tum_araclar_tek_bildirimde():
    stop = {**STOP, "bildirim_dk": 30}
    canli = [bus("114-1", 5, "A"), bus("115-1", 10, "B"), bus("115-4", 15, "C"), bus("114-1", 45, "D")]
    db, ego = FakeDb(ITEMS, [stop]), FakeEgo(canli)
    sonuc = await run_check(db, ego, NOW)
    assert len(sonuc) == 1                                  # tek bildirim
    assert [a["arac_no"] for a in sonuc[0]["araclar"]] == ["A", "B", "C"]  # 45 dk olan yok
    assert "114-1 (5 dk), 115-1 (10 dk), 115-4 (15 dk)" in sonuc[0]["mesaj"]


async def test_kullanicinin_esigi_disindaki_arac_bildirilmez():
    stop = {**STOP, "bildirim_dk": 5}
    db, ego = FakeDb(ITEMS, [stop]), FakeEgo([bus("114-1", 9, "A")])
    assert await run_check(db, ego, NOW) == []


async def test_bildirilmis_arac_tekrar_bildirilmez():
    db = FakeDb(ITEMS, [STOP], recent={("u1", "12579"): {"A"}})
    assert await run_check(db, FakeEgo([bus("114-1", 4, "A")]), NOW) == []


async def test_yeni_arac_gelince_eski_araclarla_birlikte_yeni_bildirim():
    db = FakeDb(ITEMS, [STOP], recent={("u1", "12579"): {"A"}})
    sonuc = await run_check(db, FakeEgo([bus("114-1", 4, "A"), bus("115-1", 12, "B")]), NOW)
    assert len(sonuc) == 1
    assert [a["arac_no"] for a in sonuc[0]["araclar"]] == ["A", "B"]


async def test_ayni_turda_iki_kez_bildirim_uretmez():
    db = FakeDb(ITEMS, [STOP, {**STOP}])  # aynı durak iki kez listelense bile
    sonuc = await run_check(db, FakeEgo([bus("114-1", 9, "A")]), NOW)
    assert len(sonuc) == 1


async def test_bildirim_kapaliysa_ego_ya_gidilmez():
    db, ego = FakeDb(ITEMS, [STOP], acik=False), FakeEgo([bus("114-1", 3, "A")])
    assert await run_check(db, ego, NOW) == []
    assert ego.cagri == 0


async def test_pencere_disinda_ego_ya_gitmez():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo([bus("114-1", 3, "A")])
    gec = datetime(2026, 11, 4, 7, 30, tzinfo=TZ)  # ders 09:00, pencere 08:00'de başlar
    assert await run_check(db, ego, gec) == []
    assert ego.cagri == 0


async def test_kampus_hat_listesi_bossa_veya_kampus_yoksa_bildirim_yok():
    for kw in ({"hatlar": {}}, {"kampus": None}):
        db, ego = FakeDb(ITEMS, [STOP], **kw), FakeEgo([bus("114-1", 3, "A")])
        assert await run_check(db, ego, NOW) == []
        assert ego.cagri == 0


async def test_kampus_disi_hat_filtrelenir():
    db, ego = FakeDb(ITEMS, [STOP]), FakeEgo([bus("101", 3, "A")])
    assert await run_check(db, ego, NOW) == []


async def test_ego_hatasinda_ve_eski_veride_sessizce_atlar():
    assert await run_check(FakeDb(ITEMS, [STOP]), FakeEgo(hata=True), NOW) == []
    assert await run_check(FakeDb(ITEMS, [STOP]), FakeEgo([bus("114-1", 3, "A")], stale=True), NOW) == []


async def test_bildirim_dk_bossa_varsayilan_kullanilir():
    stop = {**STOP, "bildirim_dk": None}
    db = FakeDb(ITEMS, [stop])
    assert len(await run_check(db, FakeEgo([bus("114-1", 10, "A")]), NOW)) == 1   # varsayılan 10
    db2 = FakeDb(ITEMS, [stop])
    assert await run_check(db2, FakeEgo([bus("114-1", 11, "A")]), NOW) == []


async def test_push_kayitli_cihaza_gider_ve_gonderildi_isaretlenir():
    db, push = FakeDb(ITEMS, [STOP]), FakePush()
    db.tokens = ["tok1", "tok2"]
    sonuc = await run_check(db, FakeEgo([bus("114-1", 9, "A")]), NOW, push=push)
    assert len(sonuc) == 1
    assert [g[0] for g in push.gonderilen] == ["tok1", "tok2"]
    _, baslik, govde, veri = push.gonderilen[0]
    assert baslik == "Otobüs yaklaşıyor" and "9 dk" in govde
    assert veri == {"durak_no": "12579", "notification_id": 1}
    assert db.gonderildi == [1]


async def test_gecersiz_token_silinir_digeri_gider():
    db, push = FakeDb(ITEMS, [STOP]), FakePush({"eski": "invalid"})
    db.tokens = ["eski", "yeni"]
    await run_check(db, FakeEgo([bus("114-1", 9, "A")]), NOW, push=push)
    assert db.silinen == ["eski"] and db.gonderildi == [1]


async def test_cihaz_yoksa_bildirim_kaydedilir_push_gitmez():
    db, push = FakeDb(ITEMS, [STOP]), FakePush()
    sonuc = await run_check(db, FakeEgo([bus("114-1", 9, "A")]), NOW, push=push)
    assert len(sonuc) == 1 and push.gonderilen == [] and db.gonderildi == []


async def test_push_hatasi_bildirim_kaydini_bozmaz():
    db, push = FakeDb(ITEMS, [STOP]), FakePush(hata=True)
    db.tokens = ["tok1"]
    sonuc = await run_check(db, FakeEgo([bus("114-1", 9, "A")]), NOW, push=push)
    assert len(sonuc) == 1 and len(db.inserted) == 1 and db.gonderildi == []


async def test_push_olmadan_calisir():
    db = FakeDb(ITEMS, [STOP])
    assert len(await run_check(db, FakeEgo([bus("114-1", 9, "A")]), NOW)) == 1