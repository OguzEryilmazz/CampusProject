"""Bologna araçları (kaynak_hazirla.bologna): ağ gerektirmez, ham yanıtlar önbelleğe konarak sahte post kullanılır."""
import json

import pytest

from app.rag.chunking import chunk_text
from app.rag.ingest import ingest_all
from kaynak_hazirla.bologna import cek, rag_donustur
from kaynak_hazirla.bologna.ortak import program_url, url_slug

PID = "a86f749d-cc79-4f1d-a7bf-f2eac80c306a"


def satir(i, kod, ad, y, grup=None, tip=1):
    return {"id": i, "dersKodu": kod, "dersAdi": ad, "dersAdiEng": ad, "dersTipi": tip, "yariyilNo": y,
            "kredi": 3.0, "akts": 5.0, "teorik": 3.0, "uygulama": 0.0, "laboratuvar": 0.0,
            "acilmaDurumu": "acildi", "secmeliGrupAdi": grup, "secmeliGrupKodu": None}


def ayrinti(kod, ad):
    return {"data": {
        "dersKodu": kod, "dersAdi": ad, "dersAdiEng": ad, "akademikYilAdi": "2026 - 2027", "kredi": 4.0, "akts": 5.0,
        "teorik": 4.0, "uygulama": 0.0, "laboratuvar": 0.0, "gorevliUserAdi": "DOÇ. DR. ÜMİT ERTEM",
        "egitimDiliAdi": "Türkçe", "amac": "Amaç metni.", "icerik": "İçerik metni.",
        "kazanimlar": json.dumps([{"kazanimAdi": "Limit hesaplar.", "siraNo": 1}]),
        "haftalikAkis": json.dumps([{"hafta": 1, "konu": "Limit"}, {"hafta": 2, "konu": "Türev"}]),
        "degerlendirmeYontemleri": json.dumps([{"adi": "Ara Sınav", "oran": 100}, {"adi": "Final", "oran": 100}]),
        "kaynakcalar": json.dumps([{"adi": "Kitap A"}]),
    }, "success": True}


@pytest.fixture
def veri(tmp_path):
    """backend/data/bologna ağacını ham önbellek ile hazırlar; (backend, veri) döner."""
    backend = tmp_path / "backend"
    v = backend / "data" / "bologna"
    (v / "ham" / "program").mkdir(parents=True)
    (v / "ham" / "liste").mkdir(parents=True)
    (v / "ham" / "index.json").write_text(json.dumps({"bolumler": [{"id": "bolum-" + PID, "ad": "Yazılım Mühendisliği"}]}))
    (v / "ham" / "yillar.json").write_text(json.dumps({"data": [{"no": 77, "ad": "2026 - 2027"}], "success": True}))
    (v / "ham" / "program" / f"{PID}.json").write_text(json.dumps({"data": {
        "programAdi": "Yazılım Mühendisliği", "programAdiEng": "Software Engineering",
        "akademikBirim": {"birimAdi": "Mühendislik Fakültesi"}, "dersDuzeyAdi": "Lisans",
        "hakkinda": "<p>Program hakkında.</p>", "mezuniyetKosulu": "240 AKTS tamamlanmalıdır."}, "success": True}))
    liste = [satir(None, "YMH101", "Bilgisayar Programlama I", 1),                 # id yok
             satir("id-mat", "MAT0143", "Matematik I", 1),
             satir("id-mat", "MAT0143", "Matematik I", 2, tip=2),                   # aynı ders, ikinci satır
             satir("id-yok", "YMH999", "Yayımlanmamış Ders", 3),                    # sunucu 400 verecek
             satir("id-a", "XYZ100", "Ders A", 1), satir("id-b", "XYZ100", "Ders B", 2)]  # aynı kod, farklı id
    (v / "ham" / "liste" / f"{PID}-77.json").write_text(json.dumps({"data": liste, "success": True}))
    return backend, v


@pytest.fixture
def sahte_post(monkeypatch):
    cagrilar = []

    def post(path, payload, retries=3):
        i = payload["Id"]
        cagrilar.append(i)
        if i == "id-yok":
            raise cek.KaliciHata(400, "Yayımlanmış ders bulunamadı.")
        kod, ad = {"id-mat": ("MAT0143", "Matematik I"), "id-a": ("XYZ100", "Ders A"), "id-b": ("XYZ100", "Ders B")}[i]
        return ayrinti(kod, ad)

    monkeypatch.setattr(cek, "post", post)
    return cagrilar


def cek_calistir(v, *ek):
    cek.main(["--program", "Yazılım Mühendisliği", "--liste-yolu", "/x", *ek], veri=v)
    return v / "yapisal" / f"yazilim-muhendisligi-{PID[:8]}"


def test_url_slug_ve_program_url():
    assert url_slug("Sayısal Tasarım") == "sayisaltasarim"
    assert program_url("Lisans", "Mühendislik Fakültesi", "Yazılım Mühendisliği") == \
        "https://bologna.ankara.edu.tr/programlar/lisans/muhendislikfakultesi/yazilimmuhendisligi"
    assert program_url("Doktora", "Mühendislik Fakültesi", "X") is None   # kalıp yalnızca lisans için doğrulandı


def test_cek_kimliksiz_ders_istek_atmaz_eksik_ders_kaydedilir(veri, sahte_post):
    _, v = veri
    d = cek_calistir(v)
    kayit = {k["ders_kodu"] + ("-" + k["ders_id"] if k["ders_id"] else ""): k
             for k in (json.loads(l) for l in (d / "dersler.jsonl").read_text(encoding="utf-8").splitlines())}
    assert None not in sahte_post and "id-yok" in sahte_post           # id'siz derse istek atılmadı
    assert sahte_post.count("id-mat") == 1                             # aynı ders tek kez çekildi
    assert len(kayit) == 6 - 1                                         # 6 satır, MAT0143 iki satır -> 5 ders
    assert kayit["YMH101"]["ayrinti_var"] is False
    assert kayit["YMH999-id-yok"]["ayrinti_var"] is False
    mat = kayit["MAT0143-id-mat"]
    assert mat["ayrinti_var"] and mat["yariyillar"] == [1, 2]
    assert mat["sorumlu"] == "Doç. Dr. Ümit Ertem"                      # Türkçe İ/ı bozulmuyor
    assert [x["oran_yuzde"] for x in mat["degerlendirme"]] == [None, None]   # %100 + %100: oran uydurulmaz
    assert "id yok" in (d / "eksik_dersler.txt").read_text(encoding="utf-8")


def test_cek_ikinci_calistirma_onbellekten(veri, sahte_post):
    _, v = veri
    cek_calistir(v)
    sahte_post.clear()
    cek_calistir(v)
    assert sahte_post == []                                            # her şey ham/ önbelleğinden geldi


def test_rag_donustur_benzersiz_kaynak_url_ve_ingest_cakismaz(veri, sahte_post):
    backend, v = veri
    cek_calistir(v)
    rag_donustur.main(["--backend", str(backend)])
    kaynaklar = json.loads((backend / "data" / "kaynaklar_bologna.json").read_text(encoding="utf-8"))

    assert all(k["roller"] == [] and k["fakulte"] is None for k in kaynaklar)          # herkese açık
    assert {k["tur"] for k in kaynaklar} == {"bologna_program", "bologna_mufredat", "bologna_ders"}
    kimlikler = [k["kaynak_url"] or f"dosya:{k['dosya']}" for k in kaynaklar]          # ingest.py'nin kimlik kuralı
    assert len(set(kimlikler)) == len(kaynaklar)
    assert all((backend / k["dosya"]).is_file() for k in kaynaklar)                    # yollar backend'e göreli
    assert sum(k["tur"] == "bologna_ders" for k in kaynaklar) == 5
    assert "ders-xyz100.txt" in "".join(k["dosya"] for k in kaynaklar)                 # aynı kodlu iki ders ezilmedi
    assert sum("ders-xyz100" in k["dosya"] for k in kaynaklar) == 2

    # Gerçek ingest hattından geçir: her kaynak ayrı doküman olmalı (aynı kimlik = üzerine yazma)
    db, emb = FakeDb(), FakeEmbedder()
    import asyncio
    sonuc = asyncio.run(ingest_all(db, emb, backend / "data" / "kaynaklar_bologna.json"))
    assert all(s == "yazildi" for s in sonuc.values()), sonuc
    assert len(db.docs) == len(kaynaklar)


def test_ders_metni_baslik_parcalara_tasinir_ve_not_icerir(veri, sahte_post):
    backend, v = veri
    cek_calistir(v)
    rag_donustur.main(["--backend", str(backend)])
    kaynaklar = json.loads((backend / "data" / "kaynaklar_bologna.json").read_text(encoding="utf-8"))
    mat = next(k for k in kaynaklar if k["dosya"].endswith("ders-mat0143.txt"))
    metin = (backend / mat["dosya"]).read_text(encoding="utf-8")
    assert "Haftalık konu – 2. hafta: Türev" in metin
    assert "yüzdeler verilmiyor" in metin and "%100" not in metin
    parcalar = chunk_text(metin, mat["baslik"])
    assert parcalar and all(p["icerik"].startswith("MAT0143 Matematik I – Yazılım Mühendisliği") for p in parcalar)
    ymh = next(k for k in kaynaklar if k["dosya"].endswith("ders-ymh101.txt"))
    assert "ayrıntılı ders bilgisi" in (backend / ymh["dosya"]).read_text(encoding="utf-8")


def test_rag_donustur_yeniden_calistirinca_eski_metin_kalmaz(veri, sahte_post):
    backend, v = veri
    cek_calistir(v)
    rag_donustur.main(["--backend", str(backend)])
    eski = backend / "data" / "bologna" / "metin" / "bozuk.txt"
    eski.parent.mkdir(parents=True, exist_ok=True)
    eski.write_text("silinmeli")
    rag_donustur.main(["--backend", str(backend)])
    assert not eski.exists()


class FakeEmbedder:
    async def embed(self, texts, kind="document"):
        return [[0.1, 0.2] for _ in texts]


class FakeDb:
    def __init__(self):
        self.docs, self.chunks = {}, []

    async def get_document(self, kaynak_id):
        return self.docs.get(kaynak_id)

    async def upsert_document(self, doc):
        eski = self.docs.get(doc["kaynak_id"])
        doc_id = eski["id"] if eski else len(self.docs) + 1   # gerçek veritabanı gibi: aynı kaynak aynı id
        self.docs[doc["kaynak_id"]] = {"id": doc_id, **doc}
        return doc_id

    async def delete_chunks(self, doc_id):
        self.chunks = [c for c in self.chunks if c["document_id"] != doc_id]

    async def insert_chunks(self, rows):
        self.chunks.extend(rows)
