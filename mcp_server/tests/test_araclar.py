import asyncio

import httpx

from kampus_mcp import araclar


def calistir(c):
    return asyncio.run(c)


def json_yanit(veri, durum=200):
    return lambda request: httpx.Response(durum, json=veri)


def test_profil_ve_token_iletimi(sahte_backend):
    istekler = sahte_backend(json_yanit({"ad": "A", "rol": "ogrenci", "fakulte": "Müh", "kampus": "K", "bildirim_acik": True}))
    c = calistir(araclar.profilim_getir())
    assert c["rol"] == "ogrenci" and "hata" not in c
    assert istekler[0].headers["authorization"] == "Bearer iyi-token-1234567890"
    assert str(istekler[0].url) == "http://backend.test/me"


def test_rag_aramasi_rol_fakulte_parametresi_gondermez(sahte_backend):
    istekler = sahte_backend(json_yanit({"sonuclar": []}))
    c = calistir(araclar.dokuman_ara("sınav mazeret başvurusu", 5))
    assert c["toplam_kayit"] == 0
    assert dict(istekler[0].url.params) == {"q": "sınav mazeret başvurusu"}


def test_durak_yaklasan_yoluna_yalniz_verilen_no_girer(sahte_backend):
    istekler = sahte_backend(json_yanit({"durak": "12579", "canli": [], "tarife": [], "bos": True}))
    c = calistir(araclar.durak_yaklasan_araclar("12579"))
    assert istekler[0].url.path == "/stops/12579/arrivals"
    assert c["durakta_arac_yok_veya_numara_gecersiz"] is True


def test_hata_kodlari(sahte_backend):
    beklenen = {401: "TOKEN_GECERSIZ", 403: "YETKI_YOK", 404: "KAYIT_BULUNAMADI",
                422: "PARAMETRE_GECERSIZ", 429: "ORAN_SINIRI", 500: "GECICI_HATA", 503: "GECICI_HATA"}
    for durum, kod in beklenen.items():
        sahte_backend(json_yanit({"detail": "iç hata ayrıntısı"}, durum))
        c = calistir(araclar.profilim_getir())
        assert c["hata"] is True and c["hata_kodu"] == kod
        assert "iç hata" not in c["mesaj"]  # iç metin sızmaz


def test_zaman_asimi_ve_baglanti_hatasi(sahte_backend):
    def zaman(request):
        raise httpx.ReadTimeout("x")

    def kopuk(request):
        raise httpx.ConnectError("x")

    sahte_backend(zaman)
    assert calistir(araclar.profilim_getir())["hata_kodu"] == "ZAMAN_ASIMI"
    sahte_backend(kopuk)
    assert calistir(araclar.profilim_getir())["hata_kodu"] == "GECICI_HATA"


def test_kimlik_basligi_yoksa_backend_cagrilmaz(sahte_backend, monkeypatch):
    from kampus_mcp import backend_client
    from kampus_mcp.backend_client import HataKodu

    def yok():
        raise HataKodu("KIMLIK_GEREKLI", "Oturum bilgisi bulunamadı.")

    monkeypatch.setattr(backend_client, "_auth_basligi", yok)
    istekler = sahte_backend(json_yanit({}))
    assert calistir(araclar.favori_duraklarim_getir())["hata_kodu"] == "KIMLIK_GEREKLI"
    assert istekler == []
