"""Mevzuat PDF'lerini indirir ve data/kaynaklar.json'u üretir.

Çalıştırma (backend klasöründen):
  python -m kaynak_hazirla.mevzuat.indir

- Liste kaynak_hazirla/mevzuat/liste.py içindedir; data/kaynaklar.json her çalıştırmada buradan baştan yazılır.
- İndirilen dosya gerçekten PDF mu ve metin çıkıyor mu denetlenir. Taranmış (görüntü) PDF'ten metin çıkmaz;
  o durumda uyarı verilir, RAG'a girmesi anlamsızdır.
- Hata veren bir dosya diğerlerini durdurmaz; sonda özet verilir. Hatalı olanlar kaynaklar.json'a yazılmaz.
"""
import argparse
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

from .liste import KAYNAKLAR

BACKEND = Path(__file__).resolve().parents[2]
HEADERS = {"User-Agent": "AkilliKampusAsistani-bitirme/0.1 (ogrenci projesi)"}
MIN_KARAKTER_SAYFA = 200  # sayfa başına ortalama bunun altı: büyük olasılıkla taranmış görüntü


def indir(adres, deneme=3):
    son = None
    for i in range(deneme):
        try:
            req = urllib.request.Request(adres, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            son = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"indirilemedi: {son!r}")


def pdf_metin_ozeti(veri):
    """(sayfa_sayisi, karakter_sayisi). PDF değilse ValueError."""
    if not veri.lstrip()[:5].startswith(b"%PDF"):
        raise ValueError("PDF değil (sayfa HTML ya da başka bir dosya döndü)")
    from pypdf import PdfReader
    okuyucu = PdfReader(io.BytesIO(veri))
    metin = "".join((s.extract_text() or "") for s in okuyucu.pages)
    return len(okuyucu.pages), len(metin.strip())


def main(argv=None, backend=None, kaynaklar=None, getir=indir):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=str(backend or BACKEND))
    ap.add_argument("--bekleme", type=float, default=1.0, help="indirmeler arası saniye")
    a = ap.parse_args(argv)
    kok = Path(a.backend)
    hedef = kok / "data" / "kaynaklar"
    hedef.mkdir(parents=True, exist_ok=True)

    config, sorunlar = [], []
    for ad, baslik, tur, adres in (kaynaklar if kaynaklar is not None else KAYNAKLAR):
        yol = hedef / f"{ad}.pdf"
        try:
            veri = getir(adres)
            sayfa, karakter = pdf_metin_ozeti(veri)
        except Exception as e:  # noqa: BLE001
            sorunlar.append(f"{baslik}: {e}")
            print(f"HATA   {baslik}\n       {e}")
            continue
        yol.write_bytes(veri)
        uyari = ""
        if sayfa and karakter / sayfa < MIN_KARAKTER_SAYFA:
            uyari = "  UYARI: az metin çıktı, taranmış PDF olabilir (RAG'a girmez)"
            sorunlar.append(f"{baslik}: az metin ({karakter} karakter, {sayfa} sayfa)")
        else:
            config.append({"dosya": yol.relative_to(kok).as_posix(), "baslik": baslik, "tur": tur,
                           "roller": [], "fakulte": None, "kaynak_url": adres})
        print(f"tamam  {baslik}  ({sayfa} sayfa, {karakter} karakter){uyari}")
        time.sleep(a.bekleme)

    (kok / "data" / "kaynaklar.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(config)} kaynak data/kaynaklar.json'a yazıldı, {len(sorunlar)} sorun.")
    for s in sorunlar:
        print(" -", s)
    return 1 if sorunlar else 0


if __name__ == "__main__":
    sys.exit(main())
