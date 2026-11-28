"""cek.py'nin ürettiği yapılandırılmış veriyi RAG kaynaklarına çevirir.

Girdi : data/bologna/yapisal/<program>/{program.json, mufredat.json, dersler.jsonl}
Çıktı : data/bologna/metin/<program>/*.txt   ve   data/kaynaklar_bologna.json

Yükleme (backend klasöründen):
  python -m app.rag.ingest --config data/kaynaklar_bologna.json

Notlar
- Elle yönetilen data/kaynaklar.json'a dokunmaz; Bologna için ayrı yapılandırma dosyası yazılır
  (her çalıştırmada baştan üretilir, birleştirme ve yedek derdi yok).
- chunk_text her parçanın başına 'baslik' ekler. Başlığa ders/program kimliği yazıldığı için
  "Haftalık konu – 5. hafta" gibi bir parça hangi derse ait olduğunu kaybetmez.
- ingest.py bir kaynağın kimliğini kaynak_url'den üretir; bu yüzden her kaynağın adresi benzersiz olmalı
  (program sayfası adresi + #parça). Tekrar eden adres olursa betik durur.
- Bologna herkese açıktır: roller=[] ve fakulte=null.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import ortak
from .ortak import sayi, slug

TUR_PROGRAM, TUR_MUFREDAT, TUR_DERS = "bologna_program", "bologna_mufredat", "bologna_ders"

PROGRAM_BASLIKLARI = [
    ("hakkinda", "Hakkında"),
    ("amac", "Amaç"),
    ("kayit_kabul_sartlari", "Kayıt ve Kabul Şartları"),
    ("onceki_ogrenmenin_taninmasi", "Önceki Öğrenmenin Tanınması"),
    ("ogretim_sureci", "Öğretim Süreci"),
    ("sinav_degerlendirme_notlandirma", "Sınavlar, Değerlendirme ve Notlandırma"),
    ("mezuniyet_kosulu", "Mezuniyet Koşulları"),
    ("kazanilan_derece", "Kazanılan Derece"),
    ("ust_dereceye_gecis", "Üst Derece Programlarına Geçiş"),
    ("mezunlarin_istihdam_alanlari", "Mezunların İstihdam Olanakları"),
    ("yeterlilik_ozet", "Program Yeterlilikleri (Özet)"),
]


# ---------------------------------------------------------------- metin üretimi
def metin_ders(k):
    tip = "Zorunlu" if k["ders_tipi"] == "zorunlu" else "Seçmeli"
    yy = ", ".join(f"{y}. yarıyıl" for y in k["yariyillar"]) or "yarıyıl belirtilmemiş"
    s = [
        f"Ders kodu: {k['ders_kodu']}",
        f"Ders adı: {k['ders_adi']}" + (f" ({k['ders_adi_en']})" if k.get("ders_adi_en") else ""),
        f"Program: {k['program']} ({k['fakulte']}), {k['yil']}",
        f"Yarıyıl: {yy}",
        f"Ders tipi: {tip}" + (f" (grup: {', '.join(k['secmeli_gruplar'])})" if k.get("secmeli_gruplar") else ""),
        f"Kredi: {sayi(k['kredi'])}, AKTS: {sayi(k['akts'])}",
        f"Haftalık saat: teorik {sayi(k['teorik_saat'])}, uygulama {sayi(k['uygulama_saat'])}, "
        f"laboratuvar {sayi(k['laboratuvar_saat'])}",
    ]
    if k.get("egitim_dili"):
        s.append(f"Eğitim dili: {k['egitim_dili']}")
    if k.get("sorumlu"):
        s.append(f"Dersin sorumlusu: {k['sorumlu']}")
    if not k["ayrinti_var"]:
        s.append("Bu ders için Bologna'da ayrıntılı ders bilgisi (içerik, haftalık konular, "
                 "değerlendirme) bulunmuyor; yukarıdaki bilgiler müfredat listesinden alınmıştır.")
        return "\n".join(s)
    if k.get("amac"):
        s.append(f"Dersin amacı: {k['amac']}")
    if k.get("icerik"):
        s.append(f"Dersin içeriği: {k['icerik']}")
    for i, c in enumerate(k.get("ogrenme_ciktilari") or [], 1):
        s.append(f"Öğrenme çıktısı {i}: {c}")
    for h in k.get("haftalik_konular") or []:
        s.append(f"Haftalık konu – {h['hafta']}. hafta: {h['konu']}")
    deg = k.get("degerlendirme") or []
    if deg:
        if all(x["oran_yuzde"] is not None for x in deg):
            s.append("Değerlendirme: " + "; ".join(f"{x['ad']} %{sayi(x['oran_yuzde'])}" for x in deg))
        else:
            s.append("Değerlendirme yöntemleri: " + ", ".join(x["ad"] for x in deg) +
                     " (Bologna'daki oran bilgisi tutarsız olduğundan yüzdeler verilmiyor)")
    if k.get("kaynakcalar"):
        s.append("Kaynaklar: " + "; ".join(k["kaynakcalar"]))
    return "\n".join(s)


def metin_mufredat_yariyil(rows):
    s = []
    for r in rows:
        tip = "zorunlu" if r["ders_tipi"] == "zorunlu" else "seçmeli"
        grup = f", grup: {r['secmeli_grup_adi']}" if r.get("secmeli_grup_adi") else ""
        durum = "" if r.get("acilma_durumu") in (None, "acildi") else f", durum: {r['acilma_durumu']}"
        s.append(f"{r['ders_kodu']} {r['ders_adi']} – {tip}{grup}, {sayi(r['kredi'])} kredi, "
                 f"{sayi(r['akts'])} AKTS{durum}")
    return "\n".join(s)


# ---------------------------------------------------------------- ana akış
def main(argv=None, backend=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=str(backend or ortak.BACKEND), help="backend klasörü (data/ burada)")
    ap.add_argument("--turler", default="program,mufredat",
                    help="RAG'a girecek kaynaklar: program, mufredat, ders (virgülle). Varsayılan: program,mufredat. "
                         "Ders ayrıntıları yapısal veride (dersler.jsonl) kalır, MCP araçları kesin eşleşmeyle okur.")
    a = ap.parse_args(argv)
    turler = {t.strip() for t in a.turler.split(",") if t.strip()}
    gecersiz = turler - {"program", "mufredat", "ders"}
    if gecersiz:
        sys.exit(f"Geçersiz --turler değeri: {sorted(gecersiz)} (program, mufredat, ders)")

    backend = Path(a.backend)
    veri = backend / "data" / "bologna"
    yapisal, metin_kok = veri / "yapisal", veri / "metin"
    config_fn = backend / "data" / "kaynaklar_bologna.json"

    klasorler = sorted(p.parent for p in yapisal.glob("*/program.json"))
    if not klasorler:
        sys.exit(f"{yapisal} altında program.json bulunamadı. Önce 'python -m kaynak_hazirla.bologna.cek' çalıştırın.")

    if metin_kok.exists():
        shutil.rmtree(metin_kok)  # baştan üret: silinen ders eski metin olarak kalmasın
    kaynaklar, gorulen = [], set()

    def ekle(yol, baslik, tur, metin, kaynak_url):
        if kaynak_url in gorulen:
            sys.exit(f"HATA: aynı kaynak_url iki kaynakta: {kaynak_url}")
        gorulen.add(kaynak_url)
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin.strip() + "\n", encoding="utf-8")
        kaynaklar.append({"dosya": yol.relative_to(backend).as_posix(), "baslik": baslik, "tur": tur,
                          "roller": [], "fakulte": None, "kaynak_url": kaynak_url})

    for d in klasorler:
        prog = json.loads((d / "program.json").read_text(encoding="utf-8"))
        muf = json.loads((d / "mufredat.json").read_text(encoding="utf-8"))
        dj = d / "dersler.jsonl"   # --sadece-liste ile çekilen programlarda yok; yalnızca "ders" türü için gerekir
        dersler = [json.loads(l) for l in dj.read_text(encoding="utf-8").splitlines() if l.strip()] if dj.exists() else []
        ad, yil, p_url = prog["program"], prog["yil"], prog.get("kaynak_url")
        if not p_url:  # adres kalıbı doğrulanmamış düzey: kimlik için yine de benzersiz bir değer gerekir
            p_url = f"bologna:{d.name}"
        hedef = metin_kok / d.name

        ust = [f"Program: {ad}", f"Birim: {prog['fakulte']}", f"Düzey: {prog['duzey']}"]
        for k_, e_ in (("ogretim_turu", "Öğretim türü"), ("egitim_dili", "Eğitim dili"),
                       ("egitim_yontemi", "Eğitim yöntemi")):
            if prog.get(k_):
                ust.append(f"{e_}: {prog[k_]}")
        if "program" in turler:
            ekle(hedef / "program-genel.txt", f"{ad} programı – Genel bilgiler ({yil})", TUR_PROGRAM,
                 "\n".join(ust), f"{p_url}#program-genel")
            for anahtar, etiket in PROGRAM_BASLIKLARI:
                metin = (prog["bolumler"].get(anahtar) or "").strip()
                if metin:
                    ekle(hedef / f"program-{anahtar}.txt", f"{ad} programı – {etiket} ({yil})", TUR_PROGRAM,
                         metin, f"{p_url}#program-{anahtar}")

        by = {}
        for r in muf["dersler"]:
            by.setdefault(r.get("yariyil") or 0, []).append(r)
        for y in sorted(by) if "mufredat" in turler else []:
            etiket = f"{y}. yarıyıl" if y else "yarıyıl belirtilmemiş dersler"
            ekle(hedef / f"mufredat-{y or 'belirsiz'}.txt", f"{ad} müfredatı ({yil}) – {etiket}", TUR_MUFREDAT,
                 metin_mufredat_yariyil(by[y]), f"{p_url}#mufredat-{y or 'belirsiz'}")

        kullanilan = set()
        for k in dersler if "ders" in turler else []:
            ad_dosya = slug(k["ders_kodu"])
            if ad_dosya in kullanilan:
                ad_dosya += "-" + slug(k.get("ders_id") or k["ders_adi"])[:6]
            kullanilan.add(ad_dosya)
            url = k["kaynak_url"] if k.get("kaynak_url_dogrulandi") else f"{p_url}#ders-{ad_dosya}"
            ekle(hedef / f"ders-{ad_dosya}.txt", f"{k['ders_kodu']} {k['ders_adi']} – {ad} ({yil})", TUR_DERS,
                 metin_ders(k), url)

    config_fn.write_text(json.dumps(kaynaklar, ensure_ascii=False, indent=2), encoding="utf-8")
    sayac = {}
    for k in kaynaklar:
        sayac[k["tur"]] = sayac.get(k["tur"], 0) + 1
    print(f"{len(kaynaklar)} kaynak yazıldı: {sayac}\n -> {config_fn}")


if __name__ == "__main__":
    main()
