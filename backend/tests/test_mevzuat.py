"""Mevzuat indirme betiği (kaynak_hazirla.mevzuat): ağ yok, indirme sahte fonksiyonla yapılır."""
import io
import json

from pypdf import PdfWriter

from kaynak_hazirla.mevzuat import indir
from kaynak_hazirla.mevzuat.liste import KAYNAKLAR


def metinli_pdf(metin, sayfa=1):
    """Elle yazılmış en küçük geçerli PDF: her sayfada aynı metin."""
    nesneler = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(sayfa))
    nesneler.append(f"<< /Type /Pages /Kids [{kids}] /Count {sayfa} >>")
    for i in range(sayfa):
        icerik_no = 4 + 2 * i
        nesneler.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {icerik_no} 0 R "
                        f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>")
        akis = f"BT /F1 12 Tf 50 700 Td ({metin}) Tj ET"
        nesneler.append(f"<< /Length {len(akis)} >>\nstream\n{akis}\nendstream")
    out, konumlar = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for n, g in enumerate(nesneler, 1):
        konumlar.append(out.tell())
        out.write(f"{n} 0 obj\n{g}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(nesneler) + 1}\n0000000000 65535 f \n".encode())
    for k in konumlar:
        out.write(f"{k:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(nesneler) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def bos_pdf():
    w = PdfWriter()
    w.add_blank_page(612, 792)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def test_liste_gecerli_ve_benzersiz():
    adlar = [k[0] for k in KAYNAKLAR]
    adresler = [k[3] for k in KAYNAKLAR]
    assert len(set(adlar)) == len(adlar) and len(set(adresler)) == len(adresler)
    assert all(a.startswith("https://") and a.lower().endswith(".pdf") for a in adresler)
    assert {k[2] for k in KAYNAKLAR} <= {"yonetmelik", "yonerge", "ilke", "akademik_takvim"}


def test_indir_basarili_bozuk_ve_taranmis_ayrilir(tmp_path):
    metin = "Madde 1 - Bu yonetmelik ogrenciler icindir. " * 8
    kaynaklar = [("iyi", "İyi Yönetmelik", "yonetmelik", "https://x/iyi.pdf"),
                 ("html", "HTML Dönen", "yonerge", "https://x/html.pdf"),
                 ("taranmis", "Taranmış Belge", "ilke", "https://x/tara.pdf")]
    yanit = {"https://x/iyi.pdf": metinli_pdf(metin), "https://x/html.pdf": b"<html>404</html>",
             "https://x/tara.pdf": bos_pdf()}
    kod = indir.main(["--backend", str(tmp_path), "--bekleme", "0"], kaynaklar=kaynaklar, getir=yanit.__getitem__)
    config = json.loads((tmp_path / "data" / "kaynaklar.json").read_text(encoding="utf-8"))

    assert kod == 1                                                     # sorun var -> sıfır olmayan çıkış
    assert [c["baslik"] for c in config] == ["İyi Yönetmelik"]          # bozuk ve taranmış listeye girmez
    assert config[0]["roller"] == [] and config[0]["fakulte"] is None and config[0]["kaynak_url"] == "https://x/iyi.pdf"
    assert (tmp_path / config[0]["dosya"]).is_file()
    assert not (tmp_path / "data" / "kaynaklar" / "html.pdf").exists()
