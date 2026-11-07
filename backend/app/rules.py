"""Bildirim kuralları (Senaryo 2: okula geliş). Saf fonksiyonlar, dış servis çağırmaz."""
from datetime import datetime, time, timedelta

WINDOW_BEFORE_MIN = 60   # ilk dersten kaç dk önce kontrol başlar
MAX_DAKIKA = 15          # "uygun araç": en fazla bu kadar dk uzakta
DEDUP_MIN = 30           # aynı durak için bu süre içinde tekrar bildirim yok


def parse_time(value):
    h, m = str(value).split(":")[:2]
    return time(int(h), int(m))


def first_lesson(items):
    """Günün ilk ders/mesai başlangıcı (yoksa None)."""
    starts = [parse_time(i["baslangic"]) for i in items]
    return min(starts) if starts else None


def in_window(now, start, before=WINDOW_BEFORE_MIN):
    """now, [ders - before dk, ders) aralığında mı? now saat dilimli olmalı."""
    begin = datetime.combine(now.date(), start, tzinfo=now.tzinfo)
    return begin - timedelta(minutes=before) <= now < begin


def pick_vehicle(arrivals, hatlar, max_dk=MAX_DAKIKA):
    """Kullanıcının hatlarından, en fazla max_dk uzaktaki en yakın canlı araç."""
    if arrivals.get("stale"):  # eski veriye dayanarak bildirim gönderme
        return None
    adaylar = [
        c for c in arrivals["canli"]
        if c["hat_no"] in hatlar and c["dakika"] is not None and c["dakika"] <= max_dk
    ]
    return min(adaylar, key=lambda c: c["dakika"]) if adaylar else None


def build_message(durak_ad, vehicle, lesson_start):
    ders = lesson_start.strftime("%H:%M")
    hat = vehicle["hat_no"]
    if vehicle["dakika"] == 0:
        return f"Saat {ders} dersin için {hat} numaralı otobüs {durak_ad} durağına geliyor."
    return (f"Saat {ders} dersin için {hat} numaralı otobüs "
            f"{vehicle['dakika']} dk sonra {durak_ad} durağına ulaşıyor.")