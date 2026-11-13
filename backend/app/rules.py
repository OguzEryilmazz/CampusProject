"""Bildirim kuralları (Senaryo 2: okula geliş). Saf fonksiyonlar, dış servis çağırmaz."""
from datetime import datetime, time, timedelta

WINDOW_BEFORE_MIN = 60       # ilk dersten kaç dk önce kontrol başlar
DEFAULT_BILDIRIM_DK = 10     # kullanıcı seçmediyse: otobüs durağa en fazla bu kadar dk kala haber ver
NOTIFIED_LOOKBACK_MIN = 60   # bu süre içinde bildirilen araç yeniden bildirilmez
MAX_LISTED = 5               # tek bildirimde en fazla bu kadar araç listelenir


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


def select_vehicles(arrivals, hatlar, max_dk):
    """Kullanıcının kampüs hatlarından, en fazla max_dk uzaktaki tüm canlı araçlar (yakından uzağa)."""
    if arrivals.get("stale"):  # eski veriye dayanarak bildirim gönderme
        return []
    uygun = [
        c for c in arrivals["canli"]
        if c["hat_no"] in hatlar and c["dakika"] is not None and c["dakika"] <= max_dk
    ]
    return sorted(uygun, key=lambda c: c["dakika"])


def new_vehicles(vehicles, notified):
    """Daha önce bildirilmemiş araçlar (arac_no'ya göre)."""
    return [v for v in vehicles if v["arac_no"] not in notified]


def _dk(v):
    return "geliyor" if v["dakika"] == 0 else f"{v['dakika']} dk"


def build_message(durak_ad, vehicles, lesson_start):
    ders = lesson_start.strftime("%H:%M")
    if len(vehicles) == 1:
        v = vehicles[0]
        if v["dakika"] == 0:
            return f"Saat {ders} dersin için {v['hat_no']} numaralı otobüs {durak_ad} durağına geliyor."
        return (f"Saat {ders} dersin için {v['hat_no']} numaralı otobüs "
                f"{v['dakika']} dk sonra {durak_ad} durağına ulaşıyor.")
    liste = ", ".join(f"{v['hat_no']} ({_dk(v)})" for v in vehicles)
    return f"Saat {ders} dersin için {durak_ad} durağına yaklaşan otobüsler: {liste}."