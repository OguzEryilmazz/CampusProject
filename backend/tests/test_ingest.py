import json

import pytest

from app.rag.ingest import html_to_text, ingest_all, ingest_source, read_source


class FakeEmbedder:
    def __init__(self):
        self.cagri = 0

    async def embed(self, texts):
        self.cagri += 1
        return [[0.1, 0.2] for _ in texts]


class FakeDb:
    def __init__(self):
        self.docs, self.chunks, self.silinen = {}, [], []

    async def get_document(self, kaynak_id):
        return self.docs.get(kaynak_id)

    async def upsert_document(self, doc):
        eski = self.docs.get(doc["kaynak_id"])
        doc_id = eski["id"] if eski else len(self.docs) + 1   # gerçek veritabanı gibi: aynı kaynak aynı id
        self.docs[doc["kaynak_id"]] = {"id": doc_id, **doc}
        return doc_id

    async def delete_chunks(self, doc_id):
        self.silinen.append(doc_id)
        self.chunks = [c for c in self.chunks if c["document_id"] != doc_id]

    async def insert_chunks(self, rows):
        self.chunks.extend(rows)


def yaz(tmp_path, metin, ad="a.txt"):
    (tmp_path / "data" / "kaynaklar").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "kaynaklar" / ad).write_text(metin, encoding="utf-8")
    return {"dosya": f"data/kaynaklar/{ad}", "baslik": "Y", "tur": "yonetmelik", "roller": ["ogrenci"],
            "fakulte": "Mühendislik", "kaynak_url": "https://x.edu.tr/y"}


async def test_yeni_kaynak_yazilir_metadata_parcalara_gecer(tmp_path):
    db, emb = FakeDb(), FakeEmbedder()
    entry = yaz(tmp_path, "Madde 1 – Bir.\n\nMadde 2 – İki.")
    assert await ingest_source(db, emb, entry, tmp_path) == "yazildi"
    assert len(db.chunks) == 2
    c = db.chunks[0]
    assert c["roller"] == ["ogrenci"] and c["fakulte"] == "Mühendislik" and c["kaynak_url"] == "https://x.edu.tr/y"
    assert c["embedding"] == "[0.100000,0.200000]"


async def test_degismeyen_kaynak_atlanir_degisen_yeniden_yazilir(tmp_path):
    db, emb = FakeDb(), FakeEmbedder()
    entry = yaz(tmp_path, "Madde 1 – Bir.\n\nMadde 2 – İki.")
    await ingest_source(db, emb, entry, tmp_path)
    assert await ingest_source(db, emb, entry, tmp_path) == "atlandi"
    assert emb.cagri == 1                                   # ikinci seferde vektörleme yok
    yaz(tmp_path, "Madde 1 – Bir.\n\nMadde 2 – Değişti.\n\nMadde 3 – Yeni.")
    assert await ingest_source(db, emb, entry, tmp_path) == "yazildi"
    assert db.silinen == [1] and len(db.chunks) == 3        # yalnızca güncellemede silme, yeni yazımda yok


async def test_metadata_degisince_yeniden_yazilir(tmp_path):
    db, emb = FakeDb(), FakeEmbedder()
    entry = yaz(tmp_path, "Madde 1 – Bir.\n\nMadde 2 – İki.")
    await ingest_source(db, emb, entry, tmp_path)
    assert await ingest_source(db, emb, {**entry, "roller": []}, tmp_path) == "yazildi"
    assert db.chunks[0]["roller"] == []


async def test_ingest_all_bozuk_kaynak_digerlerini_durdurmaz(tmp_path):
    ok = yaz(tmp_path, "Madde 1 – Bir.\n\nMadde 2 – İki.")
    kotu = {"dosya": "data/kaynaklar/yok.txt", "baslik": "Yok"}
    cfg = tmp_path / "data" / "kaynaklar.json"
    cfg.write_text(json.dumps([kotu, ok]), encoding="utf-8")
    sonuc = await ingest_all(FakeDb(), FakeEmbedder(), cfg)
    assert sonuc["Y"] == "yazildi" and sonuc["Yok"].startswith("hata")


def test_html_metne_cevrilir_script_atilir():
    t = html_to_text("<html><script>var x=1;</script><h1>Başlık</h1><p>Bir</p><p>İki</p></html>")
    assert "var x" not in t and t.split() == ["Başlık", "Bir", "İki"]


def make_pdf(text):
    nesneler = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    akis = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    nesneler.append(b"<< /Length %d >>\nstream\n" % len(akis) + akis + b"\nendstream")
    nesneler.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, ofs = b"%PDF-1.4\n", []
    for i, o in enumerate(nesneler, 1):
        ofs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(nesneler) + 1)
    for o in ofs:
        out += b"%010d 00000 n \n" % o
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(nesneler) + 1, x)


def test_pdf_okunur(tmp_path):
    pytest.importorskip("pypdf")
    f = tmp_path / "a.pdf"
    f.write_bytes(make_pdf("Madde 1 - Deneme metni"))
    assert "Deneme metni" in read_source(f)


def test_desteklenmeyen_tur(tmp_path):
    f = tmp_path / "a.docx"
    f.write_text("x")
    with pytest.raises(ValueError):
        read_source(f)