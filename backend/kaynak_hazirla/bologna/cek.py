"""Bologna'dan program ve ders verisini çeker, yapılandırılmış JSON olarak kaydeder.

Akış: program -> ders listesi (yıl) -> ders detayı.
Çıktı (data/bologna/ altında):
  ham/                          API yanıt önbelleği (git'e girmez; tekrar çalıştırmada yeniden çekilmez)
  yapisal/<program>/program.json, mufredat.json, dersler.jsonl, eksik_dersler.txt

Kullanım (backend klasöründen):
  python -m kaynak_hazirla.bologna.cek --program "Yazılım Mühendisliği" --en-fazla 20   # deneme
  python -m kaynak_hazirla.bologna.cek --program "Yazılım Mühendisliği"
  python -m kaynak_hazirla.bologna.cek --fakulte "Mühendislik Fakültesi" --duzey Lisans

NOT: Resmi olmayan (dokümansız) servislerdir. İstekler arasında bekleme vardır.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import ortak
from .ortak import js, program_url, slug, temiz, tr_baslik, url_slug

BEKLEME = 0.7  # saniye, istekler arası
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "AkilliKampusAsistani-bitirme/0.1 (ogrenci projesi)",
}

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


# ---------------------------------------------------------------- ağ
class KaliciHata(RuntimeError):
    """Sunucu 4xx döndü: yeniden denemek anlamsız."""

    def __init__(self, kod, mesaj):
        super().__init__(f"HTTP {kod}: {mesaj}")
        self.kod, self.mesaj = kod, mesaj


def post(path, payload, retries=3):
    data = json.dumps(payload).encode("utf-8")
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(ortak.BASE + path, data=data, headers=HEADERS, method="POST")
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
                raise KaliciHata(e.code, mesaj) from None  # tekrar denemeye değmez
            last = e
        except KaliciHata:
            raise
        except Exception as e:  # noqa: BLE001  (ağ kesintisi, zaman aşımı, 5xx)
            last = e
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{path} başarısız: {last!r}")


def cached(ham, name, path, payload):
    """Yanıtı ham/ altında saklar. Kalıcı 4xx cevapları da saklanır (ikinci kez sorulmaz)."""
    fn = Path(ham) / (name + ".json")
    if fn.exists():
        return json.loads(fn.read_text(encoding="utf-8"))
    try:
        obj = post(path, payload)
    except KaliciHata as e:
        obj = {"data": None, "success": False, "message": e.mesaj, "http": e.kod}
    fn.parent.mkdir(parents=True, exist_ok=True)
    fn.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return obj


# ---------------------------------------------------------------- yapılandırılmış kayıtlar
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
    """d: listedeki ilk satır; satirlar: aynı dersin tüm liste satırları; det: ayrıntı ya da None."""
    det = det or {}
    kaz = sorted(js(det.get("kazanimlar")), key=lambda k: k.get("siraNo", 0))
    deg = js(det.get("degerlendirmeYontemleri"))
    oran_tutarli = bool(deg) and abs(sum(float(x.get("oran") or 0) for x in deg) - 100) < 0.01
    ad = det.get("dersAdi") or d.get("dersAdi")
    kaynak = f"{ctx['program_url']}/{url_slug(ad)}" if det and ctx["program_url"] else ctx["program_url"]
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
        "kaynak_url_dogrulandi": bool(det) and ortak.DERS_URL_DOGRULANDI,
    }


def yaz_json(yol, obj):
    Path(yol).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- ana akış
def main(argv=None, veri=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", action="append", default=[], help="index.json'daki tam program adı")
    ap.add_argument("--fakulte", help="Birim adı (tüm programları tarar, yavaş)")
    ap.add_argument("--duzey", default="Lisans")
    ap.add_argument("--yil", default="2026 - 2027")
    ap.add_argument("--liste-yolu", default=os.environ.get("BOLOGNA_LISTE_YOLU") or ortak.DERS_LISTESI_YOLU,
                    help="ders listesi API yolu (ortak.py içinde ya da BOLOGNA_LISTE_YOLU)")
    ap.add_argument("--en-fazla", type=int, default=0, help="deneme için: ilk N dersle sınırla")
    a = ap.parse_args(argv)
    if not a.liste_yolu:
        sys.exit("Ders listesi yolu boş: ortak.py içindeki DERS_LISTESI_YOLU'nu doldurun ya da --liste-yolu verin.")
    if not a.program and not a.fakulte:
        sys.exit("--program ya da --fakulte verin.")

    veri = Path(veri or ortak.VERI)
    ham, yapisal = veri / "ham", veri / "yapisal"

    idx_fn = ham / "index.json"
    if not idx_fn.exists():
        ham.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(ortak.BASE + "/api/YzAsistan/index.json", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=300) as r:
            idx_fn.write_bytes(r.read())
    bolumler = json.loads(idx_fn.read_text(encoding="utf-8"))["bolumler"]

    yillar = cached(ham, "yillar", "/api/PublicMufredatDers/getYillar", {})["data"]
    yil_no = next((y["no"] for y in yillar if y["ad"].replace(" ", "") == a.yil.replace(" ", "")), None)
    if yil_no is None:
        sys.exit(f"Yıl bulunamadı: {a.yil}")

    adaylar = [b for b in bolumler if b["ad"] in a.program] if a.program else list(bolumler)
    for b in adaylar:
        pid = b["id"].removeprefix("bolum-")
        pr = cached(ham, f"program/{pid}", "/api/ProgramBilgi/getPublicByProgram", {"Id": pid})
        pb = pr.get("data")
        if not pb:
            print(f"== {b['ad']}: program bilgisi alınamadı ({pr.get('message')})")
            continue
        fakulte = (pb.get("akademikBirim") or {}).get("birimAdi") or ""
        duzey = pb.get("dersDuzeyAdi") or ""
        if a.fakulte and fakulte != a.fakulte:
            continue
        if a.duzey and duzey != a.duzey:
            continue
        ad = pb.get("programAdi") or b["ad"]
        print(f"== {ad} ({fakulte}, {duzey})")
        dizin = yapisal / (slug(ad) + "-" + pid[:8])

        lr = cached(ham, f"liste/{pid}-{yil_no}", a.liste_yolu, {"Id": pid, "Yil": a.yil, "YilNo": yil_no})
        liste = lr.get("data")
        if not liste:
            print(f"  ders listesi alınamadı: {lr.get('message')}")
            continue

        # Aynı dersi (aynı id) birden fazla grupta listelemiş olabilir. Bazı satırlarda id null:
        # onlar kod üzerinden ayrı sayılır (hepsi tek ders sanılmasın).
        satirlar_by, tekil = {}, []
        for d in liste:
            anahtar = d.get("id") or "kod:" + str(d.get("dersKodu"))
            if anahtar not in satirlar_by:
                satirlar_by[anahtar] = []
                tekil.append(d)
            satirlar_by[anahtar].append(d)
        idsiz = sum(1 for d in tekil if not d.get("id"))
        print(f"  listede {len(liste)} satır, {len(tekil)} benzersiz ders ({idsiz} tanesinde ders-bilgisi id'si yok)")
        if a.en_fazla:
            tekil = tekil[: a.en_fazla]

        ctx = {"program": ad, "program_id": pid, "fakulte": fakulte, "duzey": duzey, "yil": a.yil,
               "program_url": program_url(duzey, fakulte, ad)}
        kayitlar, eksik, hatali = [], [], []
        for n, d in enumerate(tekil, 1):
            kod = d.get("dersKodu") or "kodsuz"
            satirlar = satirlar_by[d.get("id") or "kod:" + str(d.get("dersKodu"))]
            if not d.get("id"):  # ders-bilgisi kaydı bağlanmamış: istek atma, listedeki bilgiyle kayıt yaz
                eksik.append(f"{kod} {d.get('dersAdi')} -- listede id yok")
                kayitlar.append(kayit_ders(d, satirlar, None, ctx))
                continue
            try:
                r = cached(ham, f"ders/{d['id']}", "/api/DersBilgi/getPublicById", {"Id": d["id"]})
            except RuntimeError as e:  # ağ/sunucu hatası
                hatali.append(f"{kod}: {e}")
                continue
            det = r.get("data")
            if not det:
                eksik.append(f"{kod} {d.get('dersAdi')} -- {r.get('message')}")
                kayitlar.append(kayit_ders(d, satirlar, None, ctx))
                continue
            kayitlar.append(kayit_ders(d, satirlar, det, ctx))
            if n % 25 == 0:
                print(f"  ... {n}/{len(tekil)}")

        dizin.mkdir(parents=True, exist_ok=True)
        with open(dizin / "dersler.jsonl", "w", encoding="utf-8") as f:
            for k in kayitlar:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
        yaz_json(dizin / "program.json", kayit_program(pb, ad, ctx))
        yaz_json(dizin / "mufredat.json", kayit_mufredat(liste, ctx))
        for ad_, satirlar_ in (("eksik_dersler.txt", eksik), ("hatali_dersler.txt", hatali)):
            yol = dizin / ad_
            if satirlar_:
                yol.write_text("\n".join(satirlar_) + "\n", encoding="utf-8")
            elif yol.exists():
                yol.unlink()
        detayli = sum(1 for k in kayitlar if k["ayrinti_var"])
        print(f"  {detayli} ders ayrıntılı, {len(eksik)} ayrıntısız, {len(hatali)} hatalı")

        if ctx["program_url"] and not ortak.DERS_URL_DOGRULANDI:
            ornek = [k for k in kayitlar if k["ayrinti_var"]][:3]
            ornek += [k for k in kayitlar if k["ayrinti_var"] and not k["ders_adi"].replace(" ", "").isalnum()][:2]
            print("  Ders adreslerini tarayıcıda doğrulayın (açılırsa ortak.py'de DERS_URL_DOGRULANDI = True):")
            for k in ornek:
                print("   ", k["ders_adi"], "->", k["kaynak_url"])
    print("Bitti ->", yapisal)


if __name__ == "__main__":
    main()
