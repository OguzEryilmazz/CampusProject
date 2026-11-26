import json
from pathlib import Path

import pytest

from rag_eval.metrics import (build_record, hit_matches, load_questions, markdown_report, norm,
                              stats, summarize, threshold_analysis)
from rag_eval.runner import run_eval, write_outputs


def yaz(tmp_path, data):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ---------------------------------------------------------------- soru seti
def test_ornek_soru_dosyasi_gecerli_ve_iki_turu_icerir():
    sorular = load_questions(Path(__file__).parent.parent / "rag_eval" / "sorular.ornek.json")
    assert {q["tur"] for q in sorular} == {"ilgili", "alakasiz"}
    assert {q["grup"] for q in sorular if q["tur"] == "alakasiz"} == {"tamamen_alakasiz", "alan_ici_yok"}


@pytest.mark.parametrize("veri,parca", [
    ([], "boş"),
    ([{"soru": "", "tur": "ilgili"}], "'soru'"),
    ([{"soru": "x", "tur": "belirsiz"}], "'tur'"),
    ([{"soru": "x", "tur": "ilgili"}], "'beklenen'"),
    ([{"soru": "x", "tur": "ilgili", "beklenen": [{"madde": "Madde 1"}]}], "'beklenen'"),
    ([{"soru": "x", "tur": "alakasiz", "grup": "baska"}], "'grup'"),
])
def test_hatali_soru_dosyasi_anlasilir_hata_verir(tmp_path, veri, parca):
    with pytest.raises(ValueError) as e:
        load_questions(yaz(tmp_path, veri))
    assert parca in str(e.value)


def test_alakasiz_grubu_varsayilan_tamamen_alakasiz(tmp_path):
    q = load_questions(yaz(tmp_path, [{"soru": "x", "tur": "alakasiz"}]))[0]
    assert q["grup"] == "tamamen_alakasiz"


# ---------------------------------------------------------------- eşleştirme
def test_norm_turkce_karakterler():
    assert norm("İŞ ÇIĞ Öğüt") == "is cig ogut"
    assert norm("ÖRNEK Yönetmelik") == norm("örnek yonetmelik")


def test_hit_matches_baslik_icerir_madde_esit():
    hit = {"baslik": "ÖRNEK Yönetmelik (gerçek değil)", "madde": "Madde 2"}
    assert hit_matches(hit, [{"baslik": "örnek yönetmelik", "madde": "madde 2"}])
    assert not hit_matches(hit, [{"baslik": "ÖRNEK Yönetmelik", "madde": "Madde 3"}])
    assert not hit_matches(hit, [{"baslik": "Disiplin Yönetmeliği"}])
    assert hit_matches(hit, [{"baslik": "ÖRNEK"}])                      # madde belirtilmezse yalnızca başlık
    assert hit_matches(hit, [{"baslik": "Disiplin"}, {"baslik": "ÖRNEK", "madde": "Madde 2"}])  # herhangi biri


def hit(baslik, madde, score):
    return {"baslik": baslik, "madde": madde, "score": score}


def test_build_record_sira_ve_en_yuksek_skor():
    q = {"soru": "s", "tur": "ilgili", "beklenen": [{"baslik": "Y", "madde": "Madde 2"}]}
    r = build_record(q, [hit("Y", "Madde 1", 0.7), hit("Y", "Madde 2", 0.6)])
    assert r["sira"] == 2 and r["en_yuksek"] == 0.7
    assert build_record(q, [hit("Y", "Madde 5", 0.7)])["sira"] is None
    bos = build_record({"soru": "s", "tur": "alakasiz", "grup": "alan_ici_yok"}, [])
    assert bos["en_yuksek"] == 0.0 and bos["sira"] is None


# ---------------------------------------------------------------- ölçümler
def test_stats():
    assert stats([]) is None
    s = stats([0.6, 0.8, 0.7])
    assert (s["n"], s["min"], s["medyan"], s["maks"]) == (3, 0.6, 0.7, 0.8)


def test_esik_ayrilabilir_veri():
    t = threshold_analysis([0.8, 0.75, 0.7], [0.6, 0.55, 0.5])
    assert t["guvenli"]["esik"] == 0.7 and t["guvenli"]["tpr"] == 1.0 and t["guvenli"]["fpr"] == 0.0
    assert t["onerilen"]["esik"] == 0.7 and t["onerilen"]["j"] == 1.0


def test_esik_ornek_eksikse_none():
    assert threshold_analysis([], [0.5]) is None
    assert threshold_analysis([0.7], []) is None


def kayit(tur, skor, sira=None, grup=None):
    return {"soru": f"{tur}{skor}", "tur": tur, "grup": grup, "en_yuksek": skor, "sira": sira,
            "sonuclar": [{"baslik": "Y", "madde": "Madde 1", "score": skor}]}


def test_summarize_metrikler_ve_uyarilar():
    kayitlar = [kayit("ilgili", 0.8, 1), kayit("ilgili", 0.7, 2), kayit("ilgili", 0.6, None),
                kayit("alakasiz", 0.58, grup="alan_ici_yok"), kayit("alakasiz", 0.5, grup="tamamen_alakasiz"),
                {"soru": "h", "tur": "ilgili", "hata": "429"}]
    s = summarize(kayitlar)
    assert s["n_ilgili"] == 3 and s["n_alakasiz"] == 2 and s["n_hata"] == 1
    assert s["top1"] == pytest.approx(1 / 3) and s["topk"] == pytest.approx(2 / 3)
    assert s["mrr"] == pytest.approx((1 + 0.5) / 3)
    assert set(s["alakasiz_gruplar"]) == {"alan_ici_yok", "tamamen_alakasiz"}
    metin = " ".join(s["uyarilar"])
    assert "güvenilir değil" in metin and "hata verdi" in metin


def test_summarize_ayrilamayan_skorlar_uyarir():
    s = summarize([kayit("ilgili", 0.6, 1), kayit("ilgili", 0.65, 1), kayit("alakasiz", 0.7)])
    assert s["esik"]["guvenli"] is None
    assert any("ayırt edilemiyor" in u for u in s["uyarilar"])


def test_rapor_icerigi():
    kayitlar = [kayit("ilgili", 0.8, 1), kayit("ilgili", 0.7, 2), kayit("alakasiz", 0.58, grup="alan_ici_yok")]
    s = summarize(kayitlar)
    r = markdown_report({"tarih": "t", "model_id": "gemini:x@1536", "rol": "ogrenci", "fakulte": "M", "k": 5}, kayitlar, s)
    for parca in ("gemini:x@1536", "top-1", "MRR", "Eşik önerisi", "Doğru kaynağı ilk sırada getirmeyen",
                  "Alakasız olduğu halde"):
        assert parca in r


# ---------------------------------------------------------------- çalıştırıcı
async def test_run_eval_hatayi_kaydeder_olcume_devam_eder(tmp_path):
    cagrilar = []

    async def sahte(soru, rol, fakulte, k):
        cagrilar.append((soru, rol, fakulte, k))
        if soru == "bozuk":
            raise RuntimeError("429 kota")
        return [hit("Y", "Madde 1", 0.7)]

    sorular = [{"soru": "iyi", "tur": "ilgili", "beklenen": [{"baslik": "Y", "madde": "Madde 1"}], "rol": "idari"},
               {"soru": "bozuk", "tur": "alakasiz", "grup": "alan_ici_yok"},
               {"soru": "son", "tur": "alakasiz", "grup": "tamamen_alakasiz"}]
    kayitlar = await run_eval(sorular, sahte, k=3)
    assert [("hata" in r) for r in kayitlar] == [False, True, False]
    assert cagrilar[0] == ("iyi", "idari", None, 3)                     # soruya özel rol iletilir
    assert kayitlar[0]["sira"] == 1

    s = summarize(kayitlar)
    yol, rapor = write_outputs(tmp_path / "cikti", {"model_id": "m", "k": 3}, kayitlar, s)
    assert yol.exists() and yol.with_suffix(".json").exists() and "RAG değerlendirme raporu" in rapor
    assert json.loads(yol.with_suffix(".json").read_text(encoding="utf-8"))["ozet"]["n_hata"] == 1
