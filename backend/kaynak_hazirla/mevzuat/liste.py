"""İndirilecek mevzuat kaynakları. Tek doğru kaynak bu liste: data/kaynaklar.json buradan üretilir.

Kaynak: https://oidb.ankara.edu.tr/dosyalar/ (28 Kasım 2026'da sayfadaki bağlantılardan seçildi).
Seçim ölçütü: öğrencinin sorabileceği, güncel, metin olarak okunabilen PDF'ler. Forma, personel kılavuzuna,
eski yıla ve başka kitleye (lisansüstü, konservatuvar) ait olanlar bilerek yok.
"""
OIDB = "https://oidb.ankara.edu.tr/wp-content/uploads/sites/91"

# (dosya_adı, başlık, tür, adres)
KAYNAKLAR = [
    ("egitim-ogretim-yonetmeligi", "Ankara Üniversitesi Ön Lisans ve Lisans Eğitim-Öğretim Yönetmeliği", "yonetmelik",
     f"{OIDB}/2026/04/Yonetmelik-Son-Hali-RG-Mart-2026.pdf"),
    ("gecis-cift-anadal-yandal-yonetmeligi",
     "Yükseköğretim Kurumlarında Önlisans ve Lisans Düzeyindeki Programlar Arasında Geçiş, Çift Anadal, Yan Dal ile "
     "Kurumlar Arası Kredi Transferi Yapılması Esaslarına İlişkin Yönetmelik", "yonetmelik",
     f"{OIDB}/2026/03/Ciftanadal-yandal-yonetmelik.pdf"),
    ("yaz-ogretimi-yonetmeligi", "Ankara Üniversitesi Yaz Öğretimi Yönetmeliği", "yonetmelik",
     f"{OIDB}/2024/01/ANKARA-UNIVERSITESI-YAZ-OGRETIMI-YONETMELIGI.pdf"),
    ("yabanci-dil-yonetmeligi", "Ankara Üniversitesi Yabancı Dil Eğitim-Öğretim Yönetmeliği", "yonetmelik",
     f"{OIDB}/2024/10/Yonetmelik-Son-Hali-RG-Sonrasi.pdf"),
    ("cift-anadal-yonergesi", "Ankara Üniversitesi Çift Anadal Yönergesi", "yonerge",
     f"{OIDB}/2026/04/Cift-Anadal-Yonergesi-YAYIMLANAN-2026.pdf"),
    ("yandal-yonergesi", "Ankara Üniversitesi Yandal Yönergesi", "yonerge",
     f"{OIDB}/2026/06/Yandal-Yonergesi-YAYIMLANAN-2026.pdf"),
    ("akademik-danismanlik-yonergesi", "Ankara Üniversitesi Akademik Danışmanlık Yönergesi", "yonerge",
     f"{OIDB}/2024/01/Akademik-Danismanlik-Yonergesi.pdf"),
    ("diploma-yonergesi", "Ankara Üniversitesi Diploma ve Diğer Resmî Belgelerin Düzenlenmesine İlişkin Yönerge",
     "yonerge", f"{OIDB}/2025/02/Diploma-Yonergesi-Son-Hali-06.02.2025.pdf"),
    ("sosyal-transkript-yonergesi", "Ankara Üniversitesi Sosyal Transkript Yönergesi", "yonerge",
     f"{OIDB}/2026/02/ANKARA-UNIVERSITESI-SOSYAL-TRANSKRIPT-YONERGESI.pdf"),
    ("mikro-yeterlik-yonergesi", "Ankara Üniversitesi Mikro Yeterlik Sertifikası Yönergesi", "yonerge",
     f"{OIDB}/2023/06/Ankara-Universitesi-Mikro-Yeterlik-Sertifikasi-Yonergesi.pdf"),
    ("yatay-gecis-ilkeleri", "Ankara Üniversitesi Yatay Geçiş İlkeleri (28.12.2023)", "ilke",
     f"{OIDB}/2024/03/Yatay-Gecis-Ilkeleri-28.12.2023.pdf"),
    ("ustun-basari-ilkeleri", "Üstün Başarı, Çok Üstün Başarı ve Derece Öğrencileri İçin İlkeler ve Koşullar", "ilke",
     f"{OIDB}/2025/06/Ustun-Basari-Cok-Ustun-Basari-Ogr.Ilke-Esaslari.pdf.pdf"),
    ("sinav-ilkeleri", "Ankara Üniversitesi Ön Lisans/Lisans Sınav İlkeleri", "ilke",
     f"{OIDB}/2022/02/On-Lisans-Lisans-Sinav-Ilkeleri-son.pdf"),
    ("hakli-gecerli-mazeretler", "Haklı ve Geçerli Mazeretler", "ilke",
     f"{OIDB}/2022/10/HakliveGecerliMazeretler.pdf"),
    ("ogrenci-haklari-sorumluluklari", "Öğrenci Hakları ve Sorumlulukları", "ilke",
     f"{OIDB}/2019/04/%C3%B6%C4%9Frenci-haklar%C4%B1.pdf"),
    ("bagil-degerlendirme", "Bağıl Değerlendirme Bilgi Notu", "ilke",
     "https://oidb.ankara.edu.tr/files/2014/01/Ba%C4%9F%C4%B1l-De%C4%9Ferlendirme.pdf"),
    ("akademik-takvim-2026-2027", "2026-2027 Eğitim-Öğretim Yılı Akademik Takvimi", "akademik_takvim",
     f"{OIDB}/2026/06/2026-2027_Yili_Akademik_Takvimi-SON.pdf"),
]
