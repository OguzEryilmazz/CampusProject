"""Backend yanıtlarını modelin bağlamına uygun, küçük ve tutarlı gövdelere çevirir (rehber 6.1, 6.3).
Saf fonksiyonlardır; ağ erişimi yoktur."""
from . import config


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
