"""Backend yanıtlarını modelin bağlamına uygun, küçük ve tutarlı gövdelere çevirir (rehber 6.1, 6.3).
Saf fonksiyonlardır; ağ erişimi yoktur."""
from datetime import datetime, timedelta

from . import config

GUN_ADLARI = {1: "Pazartesi", 2: "Salı", 3: "Çarşamba", 4: "Perşembe", 5: "Cuma", 6: "Cumartesi", 7: "Pazar"}


def _arac(v: dict) -> dict:
    return {
        "hat_no": v.get("hat_no"),
        "hat_ad": v.get("hat_ad"),
        "arac_no": v.get("arac_no"),
        "kalan_dakika": v.get("dakika"),
        "geliyor": bool(v.get("geliyor", False)),
    }


def _arac_listesi(canli: list[dict]) -> dict:
    # Yaklaşan araç önce: dakikası bilinmeyenler sona
    sirali = sorted(canli, key=lambda v: (v.get("dakika") is None, v.get("dakika") or 0))
    kesildi = len(sirali) > config.MAX_ARAC
    return {
        "araclar": [_arac(v) for v in sirali[: config.MAX_ARAC]],
        "toplam_arac": len(sirali),
        "kesildi": kesildi,
    }


def profil(p: dict) -> dict:
    return {
        "ad": p.get("ad"),
        "rol": p.get("rol"),
        "fakulte": p.get("fakulte"),
        "kampus": p.get("kampus"),
        "bildirim_acik": p.get("bildirim_acik", True),
    }


def favori_duraklar(duraklar: list[dict]) -> dict:
    cikti = []
    for d in duraklar:
        govde = {
            "durak_no": d.get("durak_no"),
            "ad": d.get("ad"),
            "bildirim_dk": d.get("bildirim_dk"),
            "veri_alinamadi": bool(d.get("veri_alinamadi", False)),
            "eski_veri": bool(d.get("stale", False)),
            "kampus_hat_filtresi_aktif": bool(d.get("filtre_aktif", False)),
        }
        govde.update(_arac_listesi(d.get("canli") or []))
        cikti.append(govde)
    return {"toplam_durak": len(cikti), "duraklar": cikti}


def durak_yaklasan(durak_no: str, a: dict) -> dict:
    govde = {
        "durak_no": durak_no,
        "durakta_arac_yok_veya_numara_gecersiz": bool(a.get("bos", False)),
        "eski_veri": bool(a.get("stale", False)),
        "alindi": a.get("alindi"),
        "tarife": [
            {"hat_no": t.get("hat_no"), "hat_ad": t.get("hat_ad"),
             "aciklama": t.get("aciklama"), "ilk_duraktan_kalkis": t.get("saat")}
            for t in (a.get("tarife") or [])[: config.MAX_ARAC]
        ],
    }
    govde.update(_arac_listesi(a.get("canli") or []))
    return govde


def bildirimler(liste: list[dict], limit: int) -> dict:
    limit = max(1, min(limit, config.MAX_BILDIRIM))
    secilen = liste[:limit]
    return {
        "toplam_kayit": len(liste),
        "bildirimler": [
            {"mesaj": b.get("mesaj"), "durak_no": b.get("durak_no"),
             "olusturuldu": b.get("created_at"), "push_gonderildi": b.get("sent_at") is not None}
            for b in secilen
        ],
        "kesildi": len(liste) > len(secilen),
    }


def arama(sonuc: dict, limit: int) -> dict:
    hits = sonuc.get("sonuclar") or []
    limit = max(1, min(limit, config.MAX_ARAMA_SONUCU))
    secilen = hits[:limit]
    cikti = []
    for h in secilen:
        metin = h.get("icerik") or ""
        kirpildi = len(metin) > config.ICERIK_MAX_KARAKTER
        cikti.append({
            "baslik": h.get("baslik"),
            "madde": h.get("madde"),
            "icerik": metin[: config.ICERIK_MAX_KARAKTER] + ("…" if kirpildi else ""),
            "icerik_kirpildi": kirpildi,
            "kaynak_url": h.get("kaynak_url"),
            "benzerlik": round(float(h.get("score", 0.0)), 3),
        })
    return {
        "toplam_kayit": len(hits),
        "sonuclar": cikti,
        "kesildi": len(hits) > len(secilen),
        "not": "Benzerlik puanı mutlak güven değildir; 'kaynakta yok' eşiği henüz ayarlanmadı. "
               "Sonuçlar soruyu karşılamıyorsa bunu kullanıcıya söyle, uydurma.",
    }


def _saat(v) -> str:
    return str(v)[:5]  # "09:00:00" -> "09:00"


def _ders(d: dict) -> dict:
    return {"baslangic": _saat(d.get("baslangic")), "bitis": _saat(d.get("bitis")),
            "baslik": d.get("baslik"), "yer": d.get("yer")}


def _siralli(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda d: str(d.get("baslangic")))


def hedef_gun(kapsam: str, now: datetime) -> tuple[int, str]:
    """'bugun' / 'yarin' için (gun_no, tarih). Gün numarası isoweekday'dir, Pazar'dan sonra Pazartesi gelir."""
    gun = now + timedelta(days=1) if kapsam == "yarin" else now
    return gun.isoweekday(), gun.date().isoformat()


def ders_programi(items: list[dict], kapsam: str, now: datetime) -> dict:
    if kapsam == "hafta":
        gunler = []
        for no in range(1, 8):
            dersler = _siralli([i for i in items if i.get("gun") == no])
            if dersler:
                gunler.append({"gun_no": no, "gun_adi": GUN_ADLARI[no], "dersler": [_ders(d) for d in dersler]})
        return {"kapsam": "hafta", "toplam_ders": len(items), "gunler": gunler}
    no, tarih = hedef_gun(kapsam, now)
    dersler = _siralli([i for i in items if i.get("gun") == no])
    return {
        "kapsam": kapsam, "tarih": tarih, "gun_no": no, "gun_adi": GUN_ADLARI[no],
        "toplam_ders": len(dersler),
        "ilk_ders_baslangic": _saat(dersler[0]["baslangic"]) if dersler else None,
        "dersler": [_ders(d) for d in dersler],
    }
