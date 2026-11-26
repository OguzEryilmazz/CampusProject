"""Ankara Universitesi Bologna verisini RAG icin Markdown'a cevirir.

Akis: program -> (akademik yil) -> ders listesi -> ders detayi.
Ciktilar:  out/bologna/<program>/*.md  ve  out/bologna/manifest.jsonl
Ham yanitlar raw/ altinda saklanir; betik yeniden calistirilirsa olanlari tekrar cekmez.

Ornekler:
  python scrape_bologna.py --program "Yazılım Mühendisliği"
  python scrape_bologna.py --fakulte "Mühendislik Fakültesi" --duzey Lisans

NOT: Resmi olmayan (dokumansiz) servislerdir. Istekler arasinda bekleme vardir,
ham veri onbellegi sayesinde ayni sey ikinci kez cekilmez.
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://bologna.ankara.edu.tr"

# >>> Tarayicidaki "ders listesi" isteginin yolu (govde: Id, Yil, YilNo). <<<
# Ornek: "/api/PublicMufredatDers/getPublicList"  -- Network sekmesinden kopyalayin.
DERS_LISTESI_PATH = "/api/PublicMufredatDers/getPublicList"

BEKLEME = 0.7  # saniye, istekler arasi
# Ders sayfasi adresi (program adresi + ders adi) birkac ornekle dogrulaninca True yapin.
DERS_URL_DOGRULANDI = False
RAW = "raw"
OUT = os.path.join("out", "bologna")
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "AkilliKampusAsistani-bitirme/0.1 (ogrenci projesi)",
}


# ---------------------------------------------------------------- ag
class KaliciHata(RuntimeError):
    """Sunucu 4xx dondu: yeniden denemek anlamsiz (ornegin 'Yayimlanmis ders bulunamadi')."""

    def __init__(self, kod, mesaj):
        super().__init__(f"HTTP {kod}: {mesaj}")
        self.kod, self.mesaj = kod, mesaj


def post(path, payload, retries=3):
    data = json.dumps(payload).encode("utf-8")
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=120) as r:
                obj = json.loads(r.read().decode("utf-8"))
            time.sleep(BEKLEME)
            if isinstance(obj, dict) and obj.get("success") is False:
                raise KaliciHata(200, obj.get("message"))
            return obj
        except urllib.error.HTTPError as e:
            govde = e.read().decode("utf-8", errors="replace")
            try:
                mesaj = json.loads(govde).get("message") or govde[:200]
            except ValueError:
                mesaj = govde[:200]
            time.sleep(BEKLEME)
            if 400 <= e.code < 500:
                raise KaliciHata(e.code, mesaj) from None  # tekrar denemeye degmez
            last = e
        except KaliciHata:
            raise
        except Exception as e:  # noqa: BLE001  (ag kesintisi, zaman asimi, 5xx)
            last = e
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{path} basarisiz: {last!r}")


def cached(name, path, payload):
    """Yanıtı raw/ altinda saklar. Kalici 4xx cevaplari da saklanir (ikinci kez sorulmaz)."""
    fn = os.path.join(RAW, name + ".json")
    if os.path.exists(fn):
        with open(fn, encoding="utf-8") as f:
            return json.load(f)
    try:
        obj = post(path, payload)
    except KaliciHata as e:
        obj = {"data": None, "success": False, "message": e.mesaj, "http": e.kod}
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return obj


# ---------------------------------------------------------------- yardimcilar
_TR = str.maketrans("ığüşöçİĞÜŞÖÇ", "igusocIGUSOC")


def slug(s):
    s = s.translate(_TR).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"


def temiz(s):
    """HTML etiketlerini ve fazla bosluklari temizler."""
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def js(s):
    """Icinde JSON metni olan alanlari listeye cevirir."""
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def tr_baslik(s):
    """'DOÇ. DR. ÜMİT ERTEM' -> 'Doç. Dr. Ümit Ertem' (Türkçe i/ı kurallarıyla)."""
    kucuk = s.replace("İ", "i").replace("I", "ı").lower()
    parcalar = []
    for w in kucuk.split():
        bas = w[0].replace("i", "İ").replace("ı", "I").upper()
        parcalar.append(bas + w[1:])
    return " ".join(parcalar)


def sayi(x):
    if x is None:
        return "-"
    return str(int(x)) if float(x) == int(x) else str(x)


# ---------------------------------------------------------------- Markdown
PROGRAM_BOLUMLERI = [
    ("hakkinda", "Hakkında"),
    ("amac", "Amaç"),
    ("kayitKabulSartlari", "Kayıt ve Kabul Şartları"),
    ("oncekiOgrenmeninTaninmasi", "Önceki Öğrenmenin Tanınması"),
    ("ogretimSureci", "Öğretim Süreci"),
    ("sinavlarDegerlendirmeNotlandirma", "Sınavlar, Değerlendirme ve Notlandırma"),
    ("mezuniyetKosulu", "Mezuniyet Koşulları"),
    ("kazanilanDerece", "Kazanılan Derece"),
    ("ustDereceyeGecis", "Üst Derece Programlarına Geçiş"),
    ("mezunlarinIstihdamAlanlari", "Mezunların İstihdam Olanakları"),
    ("yeterlilikOzet", "Program Yeterlilikleri (Özet)"),
]


def md_program(pb, ad):
    out = [f"# {ad} Programı", ""]
    meta = [
        ("Birim", (pb.get("akademikBirim") or {}).get("birimAdi")),
        ("Düzey", pb.get("dersDuzeyAdi")),
        ("Öğretim türü", pb.get("ogretimTurAd")),
        ("Eğitim dili", pb.get("egitimDiliAdi")),
        ("Eğitim yöntemi", pb.get("egitimYontemiAdi")),
    ]
    out += [f"- {k}: {v}" for k, v in meta if v]
    for key, baslik in PROGRAM_BOLUMLERI:
        t = temiz(pb.get(key))
        if t:
            out += ["", f"## {baslik}", t]
    return "\n".join(out) + "\n"


def md_mufredat(ad, yil, dersler):
    out = [f"# {ad} Müfredatı ({yil})", ""]
    by = {}
    for d in dersler:
        by.setdefault(d.get("yariyilNo") or 0, []).append(d)
    for y in sorted(by):
        out += [f"## {y}. Yarıyıl" if y else "## Yarıyıl belirtilmemiş"]
        for d in by[y]:
            tip = "Zorunlu" if d.get("dersTipi") == 1 else "Seçmeli"
            grup = f", grup: {d['secmeliGrupAdi']}" if d.get("secmeliGrupAdi") else ""
            durum = "" if d.get("acilmaDurumu") in (None, "acildi") else f", durum: {d['acilmaDurumu']}"
            out.append(
                f"- {d.get('dersKodu')} {d.get('dersAdi')} ({d.get('dersAdiEng')}) — {tip}{grup}, "
                f"{sayi(d.get('kredi'))} kredi, {sayi(d.get('akts'))} AKTS{durum}"
            )
        out.append("")
    return "\n".join(out)


def md_ders(d, program_ad, fakulte):
    kod, ad = d.get("dersKodu"), d.get("dersAdi")
    out = [f"# {kod} {ad} ({d.get('dersAdiEng')})", ""]
    out += [
        f"- Program: {program_ad}" + (f" ({fakulte})" if fakulte else ""),
        f"- Akademik yıl: {d.get('akademikYilAdi')}",
        f"- Düzey: {d.get('dersDuzeyiAdi')}",
        f"- Ders tipi: {d.get('dersTipiAdi')}",
        f"- Kredi: {sayi(d.get('kredi'))}, AKTS: {sayi(d.get('akts'))}",
        f"- Haftalık saat: teorik {sayi(d.get('teorik'))}, uygulama {sayi(d.get('uygulama'))}, "
        f"laboratuvar {sayi(d.get('laboratuvar'))}",
        f"- Eğitim dili: {d.get('egitimDiliAdi')}, yöntem: {d.get('egitimYontemiAdi')}",
        f"- Süre: {d.get('sureAdi')}",
    ]
    if d.get("gorevliUserAdi"):
        out.append(f"- Dersin sorumlusu: {tr_baslik(d['gorevliUserAdi'])}")
    for key, baslik in (("amac", "Dersin Amacı"), ("icerik", "Dersin İçeriği")):
        t = temiz(d.get(key))
        if t:
            out += ["", f"## {baslik}", t]

    kaz = sorted(js(d.get("kazanimlar")), key=lambda k: k.get("siraNo", 0))
    if kaz:
        out += ["", "## Öğrenme Çıktıları"]
        out += [f"{i}. {temiz(k.get('kazanimAdi'))}" for i, k in enumerate(kaz, 1)]

    hf = js(d.get("haftalikAkis"))
    if hf:
        out += ["", "## Haftalık Konular"]
        out += [f"- {h.get('hafta')}. hafta: {temiz(h.get('konu'))}" for h in hf]

    deg = js(d.get("degerlendirmeYontemleri"))
    if deg:
        out += ["", "## Değerlendirme"]
        toplam = sum(float(x.get("oran") or 0) for x in deg)
        if abs(toplam - 100) < 0.01:
            out += [f"- {x.get('adi')}: %{sayi(x.get('oran'))}" for x in deg]
        else:
            out += [f"- {x.get('adi')}" for x in deg]
            out.append("(Bologna'daki oran bilgisi tutarsız olduğundan yüzdeler yazılmadı.)")

    kay = js(d.get("kaynakcalar"))
    if kay:
        out += ["", "## Kaynaklar"] + [f"- {temiz(k.get('adi'))}" for k in kay]
    return "\n".join(out) + "\n"


def md_ders_ozet(d, program_ad, fakulte, yil):
    """Bologna'da ayrintili ders sayfasi olmayan dersler icin: yalnizca mufredat listesindeki bilgi."""
    tip = "Zorunlu" if d.get("dersTipi") == 1 else "Seçmeli"
    out = [
        f"# {d.get('dersKodu')} {d.get('dersAdi')} ({d.get('dersAdiEng')})",
        "",
        f"- Program: {program_ad}" + (f" ({fakulte})" if fakulte else ""),
        f"- Akademik yıl: {yil}",
        f"- Yarıyıl: {d.get('yariyilNo') or '-'}",
        f"- Ders tipi: {tip}",
        f"- Kredi: {sayi(d.get('kredi'))}, AKTS: {sayi(d.get('akts'))}",
        f"- Haftalık saat: teorik {sayi(d.get('teorik'))}, uygulama {sayi(d.get('uygulama'))}, "
        f"laboratuvar {sayi(d.get('laboratuvar'))}",
    ]
    if d.get("secmeliGrupAdi"):
        out.append(f"- Seçmeli ders grubu: {d['secmeliGrupAdi']}")
    out += ["", "Not: Bu ders için Bologna'da ayrıntılı ders bilgisi (içerik, haftalık konular, "
            "değerlendirme) bulunmuyor; yukarıdaki bilgiler müfredat listesinden alınmıştır."]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- yapilandirilmis cikti (MCP/RAG araclari icin)
DUZEY_URL = {"Lisans": "lisans"}  # diger duzeylerin adres bicimi dogrulanmadi


def url_slug(s):
    """Bologna adres parcasi: Turkce harfler sadelesir, bosluk ve noktalama silinir.
    'Sayısal Tasarım' -> 'sayisaltasarim' (tek ornekle dogrulandi)."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").translate(_TR).lower())


def program_url(duzey, fakulte, ad):
    d = DUZEY_URL.get(duzey)
    if not d or not fakulte:
        return None
    return f"{BASE}/programlar/{d}/{url_slug(fakulte)}/{url_slug(ad)}"


PROGRAM_ALANLARI = [
    ("hakkinda", "hakkinda"),
    ("amac", "amac"),
    ("kayitKabulSartlari", "kayit_kabul_sartlari"),
    ("oncekiOgrenmeninTaninmasi", "onceki_ogrenmenin_taninmasi"),
    ("ogretimSureci", "ogretim_sureci"),
    ("sinavlarDegerlendirmeNotlandirma", "sinav_degerlendirme_notlandirma"),
    ("mezuniyetKosulu", "mezuniyet_kosulu"),
    ("kazanilanDerece", "kazanilan_derece"),
    ("ustDereceyeGecis", "ust_dereceye_gecis"),
    ("mezunlarinIstihdamAlanlari", "mezunlarin_istihdam_alanlari"),
    ("yeterlilikOzet", "yeterlilik_ozet"),
]


def kayit_program(pb, ad, ctx):
    return {
        "program_id": ctx["program_id"],
        "program": ad,
        "program_en": pb.get("programAdiEng"),
        "fakulte": ctx["fakulte"],
        "duzey": ctx["duzey"],
        "ogretim_turu": pb.get("ogretimTurAd"),
        "egitim_dili": pb.get("egitimDiliAdi"),
        "egitim_yontemi": pb.get("egitimYontemiAdi"),
        "yil": ctx["yil"],
        "kaynak_url": ctx["program_url"],
        "bolumler": {k: (temiz(pb.get(src)) or None) for src, k in PROGRAM_ALANLARI},
    }


def kayit_mufredat(liste, ctx):
    return {
        "program_id": ctx["program_id"],
        "program": ctx["program"],
        "yil": ctx["yil"],
        "kaynak_url": ctx["program_url"],
        "dersler": [
            {
                "ders_id": d.get("id"),
                "ders_kodu": d.get("dersKodu"),
                "ders_adi": d.get("dersAdi"),
                "yariyil": d.get("yariyilNo"),
                "ders_tipi": "zorunlu" if d.get("dersTipi") == 1 else "secmeli",
                "secmeli_grup_kodu": d.get("secmeliGrupKodu"),
                "secmeli_grup_adi": d.get("secmeliGrupAdi"),
                "kredi": d.get("kredi"),
                "akts": d.get("akts"),
                "acilma_durumu": d.get("acilmaDurumu"),
            }
            for d in liste
        ],
    }


def kayit_ders(d, satirlar, det, ctx):
    """d: listedeki ilk satir; satirlar: ayni dersin tum liste satirlari; det: ayrinti ya da None."""
    det = det or {}
    kaz = sorted(js(det.get("kazanimlar")), key=lambda k: k.get("siraNo", 0))
    deg = js(det.get("degerlendirmeYontemleri"))
    oran_tutarli = bool(deg) and abs(sum(float(x.get("oran") or 0) for x in deg) - 100) < 0.01
    ad = det.get("dersAdi") or d.get("dersAdi")
    if det and ctx["program_url"]:
        kaynak = f"{ctx['program_url']}/{url_slug(ad)}"
    else:
        kaynak = ctx["program_url"]
    return {
        "ders_id": d.get("id"),
        "ders_kodu": d.get("dersKodu"),
        "ders_adi": ad,
        "ders_adi_en": det.get("dersAdiEng") or d.get("dersAdiEng"),
        "program": ctx["program"],
        "program_id": ctx["program_id"],
        "fakulte": ctx["fakulte"],
        "duzey": ctx["duzey"],
        "yil": ctx["yil"],
        "yariyillar": sorted({r["yariyilNo"] for r in satirlar if r.get("yariyilNo")}),
        "ders_tipi": "zorunlu" if d.get("dersTipi") == 1 else "secmeli",
        "secmeli_gruplar": sorted({r["secmeliGrupAdi"] for r in satirlar if r.get("secmeliGrupAdi")}),
        "kredi": det.get("kredi", d.get("kredi")),
        "akts": det.get("akts", d.get("akts")),
        "teorik_saat": det.get("teorik", d.get("teorik")),
        "uygulama_saat": det.get("uygulama", d.get("uygulama")),
        "laboratuvar_saat": det.get("laboratuvar", d.get("laboratuvar")),
        "egitim_dili": det.get("egitimDiliAdi"),
        "egitim_yontemi": det.get("egitimYontemiAdi"),
        "sorumlu": tr_baslik(det["gorevliUserAdi"]) if det.get("gorevliUserAdi") else None,
        "amac": temiz(det.get("amac")) or None,
        "icerik": temiz(det.get("icerik")) or None,
        "ogrenme_ciktilari": [temiz(k.get("kazanimAdi")) for k in kaz],
        "haftalik_konular": [
            {"hafta": h.get("hafta"), "konu": temiz(h.get("konu"))} for h in js(det.get("haftalikAkis"))
        ],
        "degerlendirme": [
            {"ad": x.get("adi"), "oran_yuzde": x.get("oran") if oran_tutarli else None} for x in deg
        ],
        "kaynakcalar": [temiz(k.get("adi")) for k in js(det.get("kaynakcalar"))],
        "ayrinti_var": bool(det),
        "program_url": ctx["program_url"],
        "kaynak_url": kaynak,
        "kaynak_url_dogrulandi": bool(det) and DERS_URL_DOGRULANDI,
    }


# ---------------------------------------------------------------- ana akis
def yaz(dizin, ad, metin, manifest, **meta):
    os.makedirs(dizin, exist_ok=True)
    yol = os.path.join(dizin, ad)
    with open(yol, "w", encoding="utf-8") as f:
        f.write(metin)
    manifest.write(json.dumps({"dosya": yol.replace("\\", "/"), **meta}, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", action="append", default=[], help="index.json'daki tam program adi")
    ap.add_argument("--fakulte", help="Birim adi (tum programlari tarar, yavas)")
    ap.add_argument("--duzey", default="Lisans")
    ap.add_argument("--yil", default="2026 - 2027")
    ap.add_argument("--liste-yolu", default=DERS_LISTESI_PATH, help="ders listesi API yolu")
    ap.add_argument("--en-fazla", type=int, default=0, help="deneme icin: ilk N dersle sinirla")
    a = ap.parse_args()
    if not a.liste_yolu:
        sys.exit("DERS_LISTESI_PATH bos. Dosyanin basindaki ayari doldurun ya da --liste-yolu verin.")
    if not a.program and not a.fakulte:
        sys.exit("--program ya da --fakulte verin.")

    # Program listesi ve yil numarasi
    idx_fn = os.path.join(RAW, "index.json")
    if not os.path.exists(idx_fn):
        os.makedirs(RAW, exist_ok=True)
        req = urllib.request.Request(BASE + "/api/YzAsistan/index.json", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=300) as r, open(idx_fn, "wb") as f:
            f.write(r.read())
    with open(idx_fn, encoding="utf-8") as f:
        bolumler = json.load(f)["bolumler"]

    yillar = cached("yillar", "/api/PublicMufredatDers/getYillar", {})["data"]
    yil_no = next((y["no"] for y in yillar if y["ad"].replace(" ", "") == a.yil.replace(" ", "")), None)
    if yil_no is None:
        sys.exit(f"Yil bulunamadi: {a.yil}")

    adaylar = [b for b in bolumler if b["ad"] in a.program] if a.program else list(bolumler)
    os.makedirs(OUT, exist_ok=True)
    for b in adaylar:
        pid = b["id"].removeprefix("bolum-")
        pr = cached(f"program/{pid}", "/api/ProgramBilgi/getPublicByProgram", {"Id": pid})
        pb = pr.get("data")
        if not pb:
            print(f"== {b['ad']}: program bilgisi alinamadi ({pr.get('message')})")
            continue
        fakulte = (pb.get("akademikBirim") or {}).get("birimAdi") or ""
        duzey = pb.get("dersDuzeyAdi") or ""
        if a.fakulte and fakulte != a.fakulte:
            continue
        if a.duzey and duzey != a.duzey:
            continue
        ad = pb.get("programAdi") or b["ad"]
        print(f"== {ad} ({fakulte}, {duzey})")
        dizin = os.path.join(OUT, slug(ad) + "-" + pid[:8])
        ortak = {"program": ad, "fakulte": fakulte, "duzey": duzey, "yil": a.yil}

        lr = cached(f"liste/{pid}-{yil_no}", a.liste_yolu, {"Id": pid, "Yil": a.yil, "YilNo": yil_no})
        liste = lr.get("data")
        if not liste:
            print(f"  ders listesi alinamadi: {lr.get('message')}")
            continue
        # ayni dersi (ayni id) birden fazla grupta listelemis olabilir
        # Bazi satirlarda id null: onlar kod uzerinden ayri sayilir (hepsi tek ders sanilmasin)
        satirlar_by, tekil = {}, []
        for d in liste:
            anahtar = d.get("id") or "kod:" + str(d.get("dersKodu"))
            if anahtar not in satirlar_by:
                satirlar_by[anahtar] = []
                tekil.append(d)
            satirlar_by[anahtar].append(d)
        idsiz = sum(1 for d in tekil if not d.get("id"))
        print(f"  listede {len(liste)} satir, {len(tekil)} benzersiz ders ({idsiz} tanesinde ders-bilgisi id'si yok)")
        if a.en_fazla:
            tekil = tekil[: a.en_fazla]

        p_url = program_url(duzey, fakulte, ad)
        ctx = {"program": ad, "program_id": pid, "fakulte": fakulte, "duzey": duzey,
               "yil": a.yil, "program_url": p_url}
        kullanilan = set()

        def dosya_adi(kod, did):
            """Ayni kodlu iki ders birbirinin ustune yazilmasin."""
            ad_ = slug(kod)
            if ad_ in kullanilan:
                ad_ = f"{ad_}-{(did or 'x')[:6]}"
            kullanilan.add(ad_)
            return ad_ + ".md"

        # Her program kendi klasorunde, kendi manifestiyle (yeniden calistirmada ust uste binmez)
        os.makedirs(dizin, exist_ok=True)
        kayitlar = []
        with open(os.path.join(dizin, "manifest.jsonl"), "w", encoding="utf-8") as manifest:
            yaz(dizin, "program.md", md_program(pb, ad), manifest, tur="program", kaynak_url=p_url, **ortak)
            yaz(dizin, "mufredat.md", md_mufredat(ad, a.yil, liste), manifest, tur="mufredat",
                kaynak_url=p_url, **ortak)
            yok, hatali, tamam = [], [], 0
            for n, d in enumerate(tekil, 1):
                kod = d.get("dersKodu") or "kodsuz"
                satirlar = satirlar_by[d.get("id") or "kod:" + str(d.get("dersKodu"))]
                if not d.get("id"):
                    # Ders-bilgisi kaydi baglanmamis: istek atma, listedeki bilgiyle ozet yaz
                    yok.append(f"{kod} {d.get('dersAdi')} -- listede id yok (ders bilgisi sayfasi baglanmamis)")
                    kayit = kayit_ders(d, satirlar, None, ctx)
                    yaz(dizin, dosya_adi(kod, None), md_ders_ozet(d, ad, fakulte, a.yil), manifest,
                        tur="ders_ozet", ders_kodu=kod, ders_adi=kayit["ders_adi"],
                        kaynak_url=kayit["kaynak_url"], **ortak)
                    kayitlar.append(kayit)
                    continue
                try:
                    r = cached(f"ders/{d['id']}", "/api/DersBilgi/getPublicById", {"Id": d["id"]})
                except RuntimeError as e:  # ag/sunucu hatasi (kalici 4xx cached icinde saklanir)
                    hatali.append(f"{d.get('dersKodu')}: {e}")
                    continue
                det = r.get("data")
                if not det:
                    yok.append(f"{d.get('dersKodu')} {d.get('dersAdi')} -- {r.get('message')}")
                    continue
                kayit = kayit_ders(d, satirlar, det, ctx)
                yaz(dizin, dosya_adi(kod, d["id"]), md_ders(det, ad, fakulte), manifest,
                    tur="ders", ders_kodu=kod, ders_adi=kayit["ders_adi"],
                    kaynak_url=kayit["kaynak_url"], **ortak)
                kayitlar.append(kayit)
                tamam += 1
                if n % 25 == 0:
                    print(f"  ... {n}/{len(tekil)}")

        # Araclarin (ders_bilgisi_getir vb.) dogrudan okuyacagi yapilandirilmis dosyalar
        with open(os.path.join(dizin, "dersler.jsonl"), "w", encoding="utf-8") as f:
            for k in kayitlar:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
        with open(os.path.join(dizin, "program.json"), "w", encoding="utf-8") as f:
            json.dump(kayit_program(pb, ad, ctx), f, ensure_ascii=False, indent=1)
        with open(os.path.join(dizin, "mufredat.json"), "w", encoding="utf-8") as f:
            json.dump(kayit_mufredat(liste, ctx), f, ensure_ascii=False, indent=1)

        if yok:
            with open(os.path.join(dizin, "yayinlanmamis_dersler.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(yok) + "\n")
        if hatali:
            with open(os.path.join(dizin, "hatali_dersler.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(hatali) + "\n")
        print(f"  {tamam} ders yazildi, {len(yok)} yayimlanmamis, {len(hatali)} hatali")

        # Ders sayfasi adreslerini elle dogrulamak icin ornekler
        if p_url and not DERS_URL_DOGRULANDI:
            detayli = [k for k in kayitlar if k["ayrinti_var"]]
            sec = detayli[:2]
            sec += [k for k in detayli if re.search(r"\b(I|II|III|IV)$", k["ders_adi"] or "")][:1]
            sec += [k for k in detayli if re.search(r"[^A-Za-zÇĞİÖŞÜçğıöşü0-9 ]", k["ders_adi"] or "")][:2]
            print("  Program adresi:", p_url)
            print("  Bu ders adreslerini tarayicida acip dogrulayin (acilirsa DERS_URL_DOGRULANDI = True):")
            for k in sec:
                print("   ", k["ders_adi"], "->", k["kaynak_url"])
    print("Bitti ->", OUT)


if __name__ == "__main__":
    main()