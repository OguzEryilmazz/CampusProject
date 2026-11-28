# Mevzuat kaynakları

Ankara Üniversitesi Öğrenci İşleri Daire Başkanlığı (https://oidb.ankara.edu.tr/dosyalar/) sayfasındaki yönetmelik,
yönerge ve ilkelerden öğrencinin soracağı olanlar RAG'a alınır. Liste `liste.py` içindedir.

```powershell
# backend klasöründen
python -m kaynak_hazirla.mevzuat.indir        # PDF'leri data/kaynaklar/ altına indirir, data/kaynaklar.json'u üretir
python -m app.rag.ingest                       # varsayılan data/kaynaklar.json
```

- `data/kaynaklar.json` bu betikle **baştan üretilir**; elle düzenleme. Kaynak eklemek için `liste.py`'ye satır ekle.
- PDF değilse (404 sayfası) ya da metin çıkmıyorsa (taranmış görüntü) kaynak listeye **girmez**, sonda uyarı yazılır.
- Bilerek alınmayanlar: formlar ve tutanaklar, öğretim elemanı/ders açma kılavuzları, geçmiş yılın akademik takvimi,
  lisansüstü ve konservatuvar belgeleri, 2547 sayılı Kanun (çok uzun, çoğu öğrenci sorusuyla ilgisiz).
- `.docx` olanlar (İntibak İlkeleri, bazı kılavuzlar) `ingest.py` tarafından henüz okunmuyor.
- Yeni sürüm yayınlanınca `liste.py`'deki adresi güncelle ve betiği yeniden çalıştır; içerik değiştiği için `ingest` günceller.
