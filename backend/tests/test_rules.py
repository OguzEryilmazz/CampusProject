from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.rules import (build_message, first_lesson, in_window, new_vehicles, parse_time,
                       select_vehicles)

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


def test_select_vehicles_hat_ve_esik_filtresi_yakindan_uzaga():
    a = arr([arac("101", 3, "a"), arac("114", 12, "b"), arac("114", 6, "c"), arac("115", 30, "d")])
    assert [v["arac_no"] for v in select_vehicles(a, {"114", "115"}, 30)] == ["c", "b", "d"]
    assert [v["arac_no"] for v in select_vehicles(a, {"114", "115"}, 10)] == ["c"]
    assert select_vehicles(a, {"999"}, 30) == []


def test_select_vehicles_esik_dahil_ve_eski_veri_bos():
    assert len(select_vehicles(arr([arac("114", 10)]), {"114"}, 10)) == 1
    assert select_vehicles(arr([arac("114", 5)], stale=True), {"114"}, 30) == []
    assert select_vehicles(arr([arac("114", None)]), {"114"}, 30) == []


def test_new_vehicles():
    v = [arac("114", 5, "a"), arac("114", 9, "b")]
    assert [x["arac_no"] for x in new_vehicles(v, {"a"})] == ["b"]
    assert new_vehicles(v, {"a", "b"}) == []


def test_build_message_tek_arac():
    assert build_message("Ev durağı", [arac("114", 10)], time(9, 0)) == \
        "Saat 09:00 dersin için 114 numaralı otobüs 10 dk sonra Ev durağı durağına ulaşıyor."
    assert "geliyor" in build_message("Ev", [arac("114", 0)], time(9, 0))


def test_build_message_birden_fazla_arac_tek_mesajda():
    m = build_message("Ev", [arac("114-1", 5), arac("115-1", 10), arac("115-4", 15)], time(9, 0))
    assert m == "Saat 09:00 dersin için Ev durağına yaklaşan otobüsler: 114-1 (5 dk), 115-1 (10 dk), 115-4 (15 dk)."
    assert "114-1 (geliyor)" in build_message("Ev", [arac("114-1", 0), arac("115-1", 8)], time(9, 0))