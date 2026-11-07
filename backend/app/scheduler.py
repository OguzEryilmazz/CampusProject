import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .ego import EgoError
from .rules import (DEDUP_MIN, build_message, first_lesson, in_window, pick_vehicle)

TZ = ZoneInfo("Europe/Istanbul")
log = logging.getLogger("scheduler")


async def run_check(db, ego, now=None):
    """Bir kontrol turu: ders penceresindeki kullanıcılar için bildirim kaydı üretir."""
    now = now or datetime.now(TZ)
    items = await db.schedule_today(now.isoweekday())

    by_user = {}
    for it in items:
        by_user.setdefault(it["user_id"], []).append(it)
    log.info("Kontrol %s: bugün (gün=%d) %d ders satırı, %d kullanıcı",
             now.strftime("%H:%M"), now.isoweekday(), len(items), len(by_user))
    adaylar = {}
    for uid, its in by_user.items():
        start = first_lesson(its)
        if start and in_window(now, start):
            adaylar[uid] = start
        else:
            log.info("  %s: ilk ders %s, ders penceresinde değil", uid[:8], start)
    if not adaylar:
        return []
    log.info("  ders penceresinde %d kullanıcı", len(adaylar))

    ids = list(adaylar)
    stops = await db.favorite_stops(ids)
    kampus_of = await db.profile_campuses(ids)
    hatlar_of = await db.campus_lines(sorted({k for k in kampus_of.values() if k}))
    recent = await db.recent_notifications(ids, now - timedelta(minutes=DEDUP_MIN))

    olusan = []
    for s in stops:
        uid, durak = s["user_id"], s["durak_no"]
        hatlar = hatlar_of.get(kampus_of.get(uid), set())
        if not hatlar:  # kampüs ya da hat listesi tanımsızsa bildirim yok
            log.info("  %s/%s: atlandı, kampüs=%r için campus_lines boş", uid[:8], durak, kampus_of.get(uid))
            continue
        if (uid, durak) in recent:
            log.info("  %s/%s: atlandı, son %d dk içinde bildirim var", uid[:8], durak, DEDUP_MIN)
            continue
        try:
            arr = await ego.arrivals(durak)
        except EgoError:
            log.info("  %s/%s: atlandı, EGO verisi alınamadı", uid[:8], durak)
            continue
        v = pick_vehicle(arr, hatlar)
        if not v:
            log.info("  %s/%s: uygun araç yok (hatlar=%s, görünen hatlar=%s, eski veri=%s)",
                     uid[:8], durak, sorted(hatlar),
                     sorted({c["hat_no"] for c in arr["canli"]}), arr.get("stale"))
            continue
        n = {
            "user_id": uid, "durak_no": durak, "arac_no": v["arac_no"],
            "hat_no": v["hat_no"], "dakika": v["dakika"],
            "mesaj": build_message(s["ad"], v, adaylar[uid]),
        }
        await db.insert_notification(n)
        recent.add((uid, durak))
        olusan.append(n)
    return olusan


async def safe_run(db, ego):
    try:
        olusan = await run_check(db, ego)
        if olusan:
            log.info("%d bildirim kaydedildi", len(olusan))
    except Exception:
        log.exception("Bildirim kontrolü başarısız")