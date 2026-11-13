import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .ego import EgoError
from .push import PushError
from .rules import (DEFAULT_BILDIRIM_DK, MAX_LISTED, NOTIFIED_LOOKBACK_MIN, build_message,
                    first_lesson, in_window, new_vehicles, select_vehicles)

TZ = ZoneInfo("Europe/Istanbul")
log = logging.getLogger("scheduler")


async def run_check(db, ego, now=None, push=None):
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
    profiles = await db.profiles(ids)
    hatlar_of = await db.campus_lines(sorted({p["kampus"] for p in profiles.values() if p["kampus"]}))
    recent = await db.recent_notifications(ids, now - timedelta(minutes=NOTIFIED_LOOKBACK_MIN))

    olusan = []
    for s in stops:
        uid, durak = s["user_id"], s["durak_no"]
        prof = profiles.get(uid, {})
        if not prof.get("bildirim_acik", True):
            log.info("  %s/%s: atlandı, kullanıcı bildirimleri kapatmış", uid[:8], durak)
            continue
        hatlar = hatlar_of.get(prof.get("kampus"), set())
        if not hatlar:  # kampüs ya da hat listesi tanımsızsa bildirim yok
            log.info("  %s/%s: atlandı, kampüs=%r için campus_lines boş", uid[:8], durak, prof.get("kampus"))
            continue
        try:
            arr = await ego.arrivals(durak)
        except EgoError:
            log.info("  %s/%s: atlandı, EGO verisi alınamadı", uid[:8], durak)
            continue

        esik = s.get("bildirim_dk") or DEFAULT_BILDIRIM_DK
        araclar = select_vehicles(arr, hatlar, esik)
        if not araclar:
            log.info("  %s/%s: %d dk içinde uygun araç yok (hatlar=%s, görünen hatlar=%s, eski veri=%s)",
                     uid[:8], durak, esik, sorted(hatlar),
                     sorted({c["hat_no"] for c in arr["canli"]}), arr.get("stale"))
            continue
        notified = recent.get((uid, durak), set())
        if not new_vehicles(araclar, notified):
            log.info("  %s/%s: atlandı, uygun araçların hepsi zaten bildirildi", uid[:8], durak)
            continue

        gosterilen = araclar[:MAX_LISTED]  # hepsi tek bildirimde, eski ve yeni araçlar birlikte
        en_yakin = gosterilen[0]
        n = {
            "user_id": uid, "durak_no": durak,
            "arac_no": en_yakin["arac_no"], "hat_no": en_yakin["hat_no"], "dakika": en_yakin["dakika"],
            "araclar": [{"arac_no": v["arac_no"], "hat_no": v["hat_no"], "dakika": v["dakika"]}
                        for v in gosterilen],
            "mesaj": build_message(s["ad"], gosterilen, adaylar[uid]),
        }
        notif_id = await db.insert_notification(n)
        if push is not None:
            try:
                await deliver(db, push, uid, notif_id, n)
            except Exception:  # push hatası bildirim kaydını ve diğer kullanıcıları etkilemesin
                log.exception("  %s/%s: push gönderimi başarısız", uid[:8], durak)
        recent.setdefault((uid, durak), set()).update(v["arac_no"] for v in gosterilen)
        olusan.append(n)
    return olusan


async def deliver(db, push, uid, notif_id, n):
    """Kullanıcının kayıtlı cihazlarına push gönderir, geçersiz token'ları siler."""
    tokens = await db.tokens_of(uid)
    if not tokens:
        log.info("  %s: kayıtlı cihaz yok, push gönderilmedi (bildirim kaydedildi)", uid[:8])
        return
    veri = {"durak_no": n["durak_no"], "notification_id": notif_id}
    gonderildi = False
    for t in tokens:
        try:
            sonuc = await push.send(t, "Otobüs yaklaşıyor", n["mesaj"], veri)
        except PushError as e:
            log.warning("  %s: push gönderilemedi: %s", uid[:8], e)
            continue
        if sonuc == "ok":
            gonderildi = True
        else:
            await db.delete_device(t)
            log.info("  %s: geçersiz cihaz token'ı silindi", uid[:8])
    if gonderildi and notif_id is not None:
        await db.mark_sent(notif_id)


async def safe_run(db, ego, push=None):
    try:
        olusan = await run_check(db, ego, push=push)
        if olusan:
            log.info("%d bildirim kaydedildi", len(olusan))
    except Exception:
        log.exception("Bildirim kontrolü başarısız")