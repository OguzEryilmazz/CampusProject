from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.rules import build_message, first_lesson, in_window, parse_time, pick_vehicle

TZ = ZoneInfo("Europe/Istanbul")


def dt(h, m):
    return datetime(2026, 11, 4, h, m, tzinfo=TZ)


def test_parse_time_saniyeli_ve_saniyesiz():
    assert parse_time("09:00:00") == time(9, 0)
    assert parse_time("13:05") == time(13, 5)


def test_first_lesson_en_erken():
    items = [{"baslangic": "13:00:00"}, {"baslangic": "09:00:00"}]
    assert first_lesson(items) == time(9, 0)
    assert first_lesson([]) is None


def test_in_window_sinirlar():
    start = time(9, 0)
    assert not in_window(dt(7, 59), start)
    assert in_window(dt(8, 0), start)
    assert in_window(dt(8, 59), start)
    assert not in_window(dt(9, 0), start)  # ders başladı


def arr(canli, stale=False):
    return {"canli": canli, "stale": stale}


def arac(hat, dk, no="x"):
    return {"hat_no": hat, "dakika": dk, "arac_no": no, "geliyor": dk == 0}


def test_pick_vehicle_hat_ve_sure_filtresi():
    a = arr([arac("101", 3), arac("114", 12, "b"), arac("114", 6, "c"), arac("114", 20, "d")])
    assert pick_vehicle(a, ["114"])["arac_no"] == "c"          # en yakın 114
    assert pick_vehicle(a, ["115"]) is None                     # hat seçili değil
    assert pick_vehicle(arr([arac("114", 20)]), ["114"]) is None  # 15 dk'dan uzak


def test_pick_vehicle_eski_veride_bildirim_yok():
    assert pick_vehicle(arr([arac("114", 5)], stale=True), ["114"]) is None


def test_pick_vehicle_dakika_bilinmiyorsa_atlar():
    assert pick_vehicle(arr([arac("114", None)]), ["114"]) is None


def test_build_message():
    assert build_message("Ev durağı", arac("114", 10), time(9, 0)) == \
        "Saat 09:00 dersin için 114 numaralı otobüs 10 dk sonra Ev durağı durağına ulaşıyor."
    assert "geliyor" in build_message("Ev", arac("114", 0), time(9, 0))