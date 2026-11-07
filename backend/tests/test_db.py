from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.db import Db


async def test_sorgular_dogru_adres_ve_basliklarla_gider():
    istekler = []

    def handler(req):
        istekler.append(req)
        if req.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[{"user_id": "u1", "durak_no": "12579"}])

    db = Db("https://x.supabase.co", "gizli", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await db.schedule_today(3)
    kume = await db.recent_notifications(["u1", "u2"], datetime(2026, 11, 4, 8, 0, tzinfo=ZoneInfo("Europe/Istanbul")))
    await db.insert_notification({"user_id": "u1"})

    assert kume == {("u1", "12579")}
    assert str(istekler[0].url).startswith("https://x.supabase.co/rest/v1/schedule_items")
    assert istekler[0].url.params["gun"] == "eq.3"
    assert istekler[0].headers["apikey"] == "gizli"
    assert istekler[1].url.params["user_id"] == "in.(u1,u2)"
    assert istekler[1].url.params["created_at"] == "gte.2026-11-04T05:00:00+00:00"  # UTC'ye çevrilmiş
    assert istekler[2].method == "POST" and istekler[2].headers["prefer"] == "return=minimal"


async def test_kampus_hatlari_tirnakli_in_filtresi_ve_gruplama():
    istek = {}

    def handler(req):
        istek["r"] = req
        return httpx.Response(200, json=[
            {"kampus": "Gölbaşı 50. Yıl", "hat_no": "114-1"},
            {"kampus": "Gölbaşı 50. Yıl", "hat_no": "115-1"}])

    db = Db("https://x.supabase.co", "k", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    sonuc = await db.campus_lines(["Gölbaşı 50. Yıl", "Tandoğan"])
    assert sonuc == {"Gölbaşı 50. Yıl": {"114-1", "115-1"}}
    assert istek["r"].url.params["kampus"] == 'in.("Gölbaşı 50. Yıl","Tandoğan")'