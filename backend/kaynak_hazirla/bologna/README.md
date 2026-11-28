# Bologna kaynakları

Ankara Üniversitesi Bologna sitesinden program ve ders bilgisini çeker, RAG ve MCP araçları için hazırlar.
Servisler **resmi olmayan** (dokümansız) uç noktalardır; değişebilir ya da kapanabilir, bitirme raporunda böyle belirtilmeli.

## Dosya yapısı

```
backend/
  kaynak_hazirla/bologna/        kod (python -m ile çalışır, rag_eval gibi)
    ortak.py                     adresler, ayarlar, küçük yardımcılar
    cek.py                       Bologna -> yapısal JSON
    rag_donustur.py              yapısal JSON -> RAG metinleri + kaynak listesi
  data/
    kaynaklar.json               ELLE yönetilen kaynaklar (yönetmelik, duyuru)
    kaynaklar/                   onların dosyaları
    kaynaklar_bologna.json       ÜRETİLİR (rag_donustur.py), ingest --config ile yüklenir
    bologna/
      ham/                       API yanıt önbelleği, git'e GİRMEZ (index.json ~14 MB)
      yapisal/<program>/         program.json, mufredat.json, dersler.jsonl  (MCP araçları bunu okur)
      metin/<program>/           ders-*.txt, mufredat-*.txt, program-*.txt   (RAG'a giren metin)
```

`kaynaklar_bologna.json`, `yapisal/` ve `metin/` üretilir ama commit edilir: sunucu imajı Bologna'ya bağlanmadan
yüklenebilsin ve değişiklikler diff'te görünsün. Yalnızca `ham/` git dışıdır.

## Çalıştırma (backend klasöründen)

```powershell
# 0) bir kerelik: ortak.py içindeki DERS_LISTESI_YOLU'nu doldur (tarayıcı Network sekmesinden ders listesi isteği)
python -m kaynak_hazirla.bologna.cek --program "Yazılım Mühendisliği" --en-fazla 20    # deneme
python -m kaynak_hazirla.bologna.cek --program "Yazılım Mühendisliği"
python -m kaynak_hazirla.bologna.rag_donustur          # varsayılan: yalnızca program + müfredat metni RAG'a girer
python -m app.rag.ingest --config data/kaynaklar_bologna.json
```

Tüm lisans mühendislik programları: `cek --fakulte "Mühendislik Fakültesi" --duzey Lisans`.
İkinci çalıştırma `ham/` önbelleğinden gelir; yeni veri için `ham/` içindeki ilgili dosyayı (ya da klasörü) sil.

## RAG'a ne girer, ne girmez

Varsayılan olarak yalnızca **program metinleri** (mezuniyet koşulu, sınav/notlandırma…) ve **yarıyıl müfredat listeleri** RAG'a girer
(`--turler program,mufredat`). **Ders ayrıntıları** (`dersler.jsonl`) vektöre konmaz: ders kodu, AKTS, haftalık konu gibi kesin
bilgiler, kullanıcının programı bilindiğinde MCP aracıyla tam eşleşmeyle okunur. Tüm fakülte için ders başına belge
binlerce kaynak ve aynı adlı derslerin (Fizik I…) birbirine karışması demektir. Gerekirse `--turler program,mufredat,ders` ile açılır.

## Bilinen noktalar

- **Ders sayfası adresi** `…/programlar/lisans/<fakulte>/<program>/<ders adı>` kalıbı tek örnekle doğrulandı
  (`sayisaltasarim`). `cek.py` çalışırken birkaç adres yazar; hepsi tarayıcıda açılırsa `ortak.py`'de
  `DERS_URL_DOGRULANDI = True` yap, ardından `cek` ve `rag_donustur`'u yeniden çalıştır. O zamana kadar
  `kaynak_url` program sayfası + `#parça` olur (benzersiz olmak zorunda: `ingest.py` kaynağın kimliğini adresten üretir).
- **Ders-bilgisi kimliği olmayan dersler** (listede `id` null) için istek atılmaz; yalnızca müfredat bilgisiyle
  `ayrinti_var: false` kaydı üretilir. Sayıları `yapisal/<program>/eksik_dersler.txt` içinde.
- **Değerlendirme oranları** toplamı 100 değilse (kaynakta bozuk veri var) `oran_yuzde: null` yazılır, yüzde uydurulmaz.
- **Bologna herkese açıktır:** `roller: []`, `fakulte: null`. `match_chunks` SQL fonksiyonunun boş rolü "herkese açık"
  saydığı doğrulanmalı.
- Akademik kadro (ad, e-posta) bilerek alınmıyor.

## MCP araçları için sözleşme: `dersler.jsonl`

Her satır bir ders. Alan adları **sözleşmedir**, yeniden adlandırmak MCP araçlarını bozar; yeni alan eklemek serbest.

| Alan | Anlamı |
|---|---|
| `ders_id`, `ders_kodu`, `ders_adi`, `ders_adi_en` | kimlik ve ad (`ders_id` ayrıntısız derslerde `null` olabilir) |
| `program`, `program_id`, `fakulte`, `duzey`, `yil` | bağlam |
| `yariyillar` | dersin verildiği yarıyıllar (liste) |
| `ders_tipi` | `zorunlu` ya da `secmeli`; `secmeli_gruplar` seçmeli grup adları |
| `kredi`, `akts`, `teorik_saat`, `uygulama_saat`, `laboratuvar_saat` | sayısal alanlar |
| `amac`, `icerik`, `ogrenme_ciktilari[]`, `haftalik_konular[{hafta,konu}]` | ayrıntı (`ayrinti_var: false` ise boş) |
| `degerlendirme[{ad, oran_yuzde}]` | `oran_yuzde` tutarsız veride `null` |
| `kaynakcalar[]`, `sorumlu`, `egitim_dili`, `egitim_yontemi` | diğer |
| `ayrinti_var` | Bologna'da ayrıntılı ders sayfası var mı |
| `program_url`, `kaynak_url`, `kaynak_url_dogrulandi` | kaynak gösterme; doğrulanmamışsa `program_url` kullan |

`program.json` bölüm anahtarları `bolumler{}` altındadır (`mezuniyet_kosulu`, `sinav_degerlendirme_notlandirma`, …);
`mufredat.json` yarıyıl bazlı satır listesidir (aynı ders birden çok satırda olabilir).

## Testler

`python -m pytest tests/test_bologna.py` (ağ gerektirmez).
