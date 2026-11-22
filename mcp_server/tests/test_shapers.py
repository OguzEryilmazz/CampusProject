from kampus_mcp import config, shapers


def arac(no, dk, hat="114-1"):
    return {"hat_no": hat, "hat_ad": "H", "arac_no": no, "dakika": dk, "geliyor": dk == 0}


def test_araclar_yakin_olan_once_ve_bilinmeyen_sonda():
    cikti = shapers._arac_listesi([arac("a", None), arac("b", 9), arac("c", 2)])
    assert [a["arac_no"] for a in cikti["araclar"]] == ["c", "b", "a"]
    assert cikti["toplam_arac"] == 3 and cikti["kesildi"] is False


def test_arac_listesi_ust_sinira_kirpilir_ve_bildirir():
    cikti = shapers._arac_listesi([arac(str(i), i) for i in range(config.MAX_ARAC + 5)])
    assert len(cikti["araclar"]) == config.MAX_ARAC
    assert cikti["toplam_arac"] == config.MAX_ARAC + 5 and cikti["kesildi"] is True


def test_bos_sonuc_alanlari_atlamaz():
    cikti = shapers.favori_duraklar([])
    assert cikti == {"toplam_durak": 0, "duraklar": []}
    d = shapers.favori_duraklar([{"durak_no": "1", "ad": "x", "bildirim_dk": 10}])["duraklar"][0]
    assert d["araclar"] == [] and d["toplam_arac"] == 0 and d["veri_alinamadi"] is False


def test_favori_duraklar_gereksiz_alan_dondurmez():
    d = shapers.favori_duraklar([{"id": 7, "durak_no": "1", "ad": "x", "bildirim_dk": 10,
                                  "canli": [{**arac("a", 3), "sure_ham": "3 dk", "detay": "Körüklü"}]}])["duraklar"][0]
    assert "id" not in d and "sure_ham" not in d["araclar"][0] and "detay" not in d["araclar"][0]


def test_bildirimler_limit_ve_push_durumu():
    liste = [{"mesaj": f"m{i}", "durak_no": "1", "created_at": "t", "sent_at": "s" if i == 0 else None} for i in range(30)]
    c = shapers.bildirimler(liste, 3)
    assert len(c["bildirimler"]) == 3 and c["kesildi"] is True and c["toplam_kayit"] == 30
    assert c["bildirimler"][0]["push_gonderildi"] is True and c["bildirimler"][1]["push_gonderildi"] is False
    assert len(shapers.bildirimler(liste, 999)["bildirimler"]) == config.MAX_BILDIRIM


def test_arama_uzun_metni_kirpar_ve_isaretler():
    uzun = "a" * (config.ICERIK_MAX_KARAKTER + 50)
    c = shapers.arama({"sonuclar": [{"icerik": uzun, "baslik": "Yönetmelik", "madde": "Madde 5", "score": 0.81234}]}, 5)
    s = c["sonuclar"][0]
    assert s["icerik_kirpildi"] is True and s["icerik"].endswith("…") and s["benzerlik"] == 0.812
    assert s["madde"] == "Madde 5"


def test_arama_bos_sonuc():
    c = shapers.arama({"sonuclar": []}, 5)
    assert c["toplam_kayit"] == 0 and c["sonuclar"] == []
