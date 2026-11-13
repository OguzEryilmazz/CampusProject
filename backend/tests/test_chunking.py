from app.rag.chunking import MAX_CHARS, chunk_text, normalize

YONETMELIK = """ÖRNEK YÖNETMELİK

Madde 1 – Amaç hükmü.

Madde 2 – Mazeret sınavı için başvuru yapılır.

GEÇİCİ MADDE 1 – Geçiş hükmü.
"""


def test_maddeler_ayri_parca_ve_baslik_eklenir():
    p = chunk_text(YONETMELIK, "Yönetmelik")
    maddeler = [x["madde"] for x in p]
    assert maddeler == [None, "Madde 1", "Madde 2", "GEÇİCİ MADDE 1"]
    assert p[2]["icerik"].startswith("Yönetmelik – Madde 2\n")
    assert "Mazeret sınavı" in p[2]["icerik"] and "Amaç" not in p[2]["icerik"]


def test_madde_yoksa_paragraf_parcalama():
    p = chunk_text("Birinci paragraf.\n\nİkinci paragraf.", "Duyuru")
    assert len(p) == 1 and p[0]["madde"] is None
    assert p[0]["icerik"] == "Duyuru\nBirinci paragraf.\nİkinci paragraf."


def test_uzun_madde_bolunur_ve_ortusur():
    cumle = "Bu bir deneme cümlesidir ve oldukça uzundur. "
    metin = "Madde 1 – " + cumle * 80 + "\n\nMadde 2 – Kısa madde."
    p = chunk_text(metin, "Y")
    m1 = [x for x in p if x["madde"] == "Madde 1"]
    assert len(m1) > 1
    assert all(len(x["icerik"]) <= MAX_CHARS + 120 for x in m1)   # başlık payı
    assert [x for x in p if x["madde"] == "Madde 2"][0]["icerik"].endswith("Kısa madde.")
    # örtüşme: ikinci parçanın başı birincinin sonundan kelimeler içerir
    assert m1[0]["icerik"].split()[-1] in m1[1]["icerik"]


def test_bosluk_ve_bos_metin():
    assert chunk_text("  \n\n ", "X") == []
    assert normalize("a\r\n\r\n\r\n\r\nb  c") == "a\n\nb c"


def test_noktalamasiz_dev_metin_sonsuz_donguye_girmez():
    p = chunk_text("a" * 5000, "X")
    assert len(p) >= 4 and all(len(x["icerik"]) <= MAX_CHARS + 20 for x in p)