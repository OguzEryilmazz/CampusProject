# Akıllı Kampüs Asistanı – Proje Raporu

Bitirme projesi · Ankara Üniversitesi Yazılım Mühendisliği · Sürüm 0.2 · 4 Kasım 2026

## 1. Özet

Akıllı Kampüs Asistanı, Ankara Üniversitesi öğrencilerinin ve personelinin ulaşım belirsizliğini azaltan ve okulun dağınık bilgisini (yönetmelikler, duyurular, bültenler) tek uygulamada toplayan bir mobil uygulamadır. Kullanıcı favori duraklarını ekler; sistem ders programına ve EGO canlı verisine bakarak "Dersin 10 dk içinde bitiyor, 101 durağına araç 10 dk sonra geliyor, kaçırmak üzeresin" gibi bildirimler gönderir. Bu bildirimler LLM gerektirmeden, kural tabanlı çalışır.

Okul dokümanları RAG ile indekslenir ve bir MCP sunucusu üzerinden LLM asistanına bağlanır. Kullanıcı yönetmelikleri ve duyuruları sohbetle sorgular, asistan kaynak bağlantısıyla cevaplar. Pilot kapsamı Gölbaşı 50. Yıl Yerleşkesi ve Tandoğan Kampüsü çevresindeki duraklar ile sahte (mock) kullanıcı verisiyle sınırlıdır. Sistem iterasyonlarla adım adım canlıya alınır.

## 2. Amaç ve kapsam

**Amaç:** Üniversite topluluğunun okul bilgisine ve ulaşıma tek yerden, kişiselleştirilmiş ve proaktif biçimde erişmesini sağlamak.

**Kapsam içi:** Flutter mobil istemci (önce Android), FastAPI backend, favori durak ve ders programı, canlı EGO verisiyle kural tabanlı bildirim, rol ve fakülte bazlı duyuru akışı, okul kaynakları için RAG, MCP sunucusu, LLM sohbet asistanı. Pilot: Gölbaşı 50. Yıl ve Tandoğan çevresindeki duraklar, mock kullanıcı verisi.

**Kapsam dışı (şimdilik):** web istemcisi, gerçek OBS entegrasyonu, tüm Ankara hatları, diğer şehirler ve üniversiteler, anlık konum takibi, ödeme ve kart işlemleri, geçmiş veriyle tahmin modeli. Bunlar raporda "Gelecek çalışmalar" olarak yer alır.

## 3. Mevcut durum (2 Kasım 2026)

- EGO servisi (`egocptsrvand.ego.gov.tr/mblSrv14/service.asp`) denendi, çalışıyor ve canlı araç satırları EGO Cep uygulamasıyla karşılaştırılıp doğrulandı.
- Cevap alanları: `arac_no`, `sure`, `detay`, `hat_kod`, `hat_no`, `hat_kisa_kod`, `hat_ad`. Canlı araçlarda `arac_no` doludur ve `sure` bu durağa kalan dakikadır. Tarife satırlarında `arac_no` "-" olur.
- EgoPy'nin eski sunucusu (88.255.141.70) 504 veriyor, kullanılmayacak.
- Veri, backend üzerinden sorgulanır ve 30-45 sn önbelleğe alınır. Mobil cihaz EGO'ya doğrudan istek atmaz. Uzun veri toplama ve `collector.py` kullanılmayacak.
- Veri kaynağı resmi olmayan bir endpoint'tir. Raporda bu açıkça belirtilecektir.

## 4. Kullanıcılar ve senaryolar

**Kullanıcı grupları:** öğrenci (ders ve otobüs odaklı), öğretim elemanı (ders programı, duyuru, kampüse varış), idari çalışan (mesai, servis, duyuru). İçerik ve bildirimler rolüne göre filtrelenir.

**Örnek senaryolar:**

1. **Ders bitişi (günde bir kez, kural tabanlı).** Backend her gün öğrencinin ders programına bir kez bakar. Son ders bitmeden kısa süre önce seçili kampüs durağı için EGO'yu bir kez sorgular, kalan süreyi sabit yürüme süresiyle karşılaştırır ve "Dersin 10 dk içinde bitiyor, 101 durağına araç 10 dk sonra geliyor, kaçırmak üzeresin" gibi bildirim gönderir. Konum alınmaz, LLM kullanılmaz.
2. **Okula geliş (favori durak).** İlk dersten yaklaşık 1 saat önce favori durak için canlı veri kontrolü başlar. Uygun araç varsa "09:00'daki dersin için 114 numaralı otobüs 10 dk sonra favori durağına ulaşıyor" bildirimi gider.
3. **Rol ve fakülte bazlı duyuru akışı.** Gece 03:00'te okul kaynakları taranır, yeni içerik rol ve fakülte etiketiyle indekslenir. Sabah uygulamayı açan Mühendislik Fakültesi öğretim üyesi ana sayfada yalnızca ilgili duyuruları görür.
4. **Soru-cevap (RAG + MCP).** "Mazeret sınavı hakkım kaç gün?" sorusuna asistan yönetmelikten kaynak bağlantısıyla cevap verir, kaynakta bulamazsa bulamadığını söyler.
5. **Serbest sohbet.** "Yarın ilk dersime nasıl yetişirim?" sorusunda LLM, MCP tool'larıyla ders programını ve EGO verisini birleştirip cevap verir.

## 5. İşlevsel gereksinimler

Öncelik: **Z** = zorunlu (MVP), **Ö** = olması gereken, **İ** = isteğe bağlı.

| No | Gereksinim | Öncelik |
|---|---|---|
| FR-1 | Mock kullanıcı veri setiyle giriş (Supabase Auth), rol (öğrenci, akademisyen, idari personel) ve fakülte ataması, ders ve mesai programının tutulması. | Z |
| FR-2 | Kullanıcı favori durak ekleyip çıkarabilir. | Z |
| FR-3 | EGO verisi backend üzerinden sorgulanır, durak bazlı 30-45 sn önbelleklenir, canlı araç ve tarife satırları ayrıştırılır. | Z |
| FR-4 | EGO yanıt vermezse kullanıcıya "Canlı veri alınamıyor, resmi tarifeye bakınız" denir. | Ö |
| FR-5 | Zamanlayıcı (APScheduler), ders programına göre günlük kural tabanlı bildirim işleri çalıştırır. LLM kullanılmaz. | Z |
| FR-6 | Bildirim kuralları: aynı araç için tekrar bildirim yok, sessiz saatler, kullanıcı bildirimi kapatabilir. | Z |
| FR-7 | Kampüs durakları için sabit yürüme süresi tablosu bulunur. | Z |
| FR-8 | Gece 03:00 tam tarama ve gün içinde RSS ile hafif kontrol yapan kazıyıcı. Başlangıçta 3-5 kaynak taranır. | Z |
| FR-9 | İçerik parçalanır, Türkçe destekli çok dilli embedding ile pgvector'e yazılır, rol ve fakülte etiketi kaynaktan atanır. | Z |
| FR-10 | RAG sorgusu rol ve fakülte filtresiyle çalışır, cevap kaynak bağlantısı içerir, kaynakta yoksa bulamadığını söyler. | Z |
| FR-11 | MCP sunucusu tool'ları: `get_ego_live_data`, `search_university_docs`, `get_schedule`, `get_favorite_stops`, `get_user_role`. | Z |
| FR-12 | LLM sohbet asistanı yalnızca kullanıcı mesajlaştığında çağrılır. | Z |
| FR-13 | Ana sayfada "Sana özel duyurular" alanı (rol ve fakülte bazlı). | Ö |
| FR-14 | Gönderilen bildirimdeki süre ile otobüsün gerçek gelişi kaydedilir, sistemin doğruluğu ölçülür. | İ |
| FR-15 | Yeni duyuru çıkınca ilgili role push bildirimi. | İ |

## 6. İşlevsel olmayan gereksinimler

- **NFR-1 Güvenilirlik:** EGO yanıt vermezse son geçerli veri yaşıyla birlikte gösterilir ve kullanıcı uyarılır.
- **NFR-2 İçerik güncelliği:** Gece tam tarama ve gün içi RSS kontrolüyle değişen içerik RAG indeksine yeniden yazılır.
- **NFR-3 Gizlilik ve erişim:** Pilotta mock veri kullanılır ve konum alınmaz. İleride gerçek kullanıcıya geçilirse açık rıza (KVKK) alınır ve konum saklanmaz. Rol ve fakülte kısıtı, prompt'ta değil vektör sorgusunun metadata filtresinde uygulanır.
- **NFR-4 Kaynağa saygı:** EGO'ya kullanıcı başına değil durak başına paylaşılan sorgu ve önbellek kullanılır. Okul siteleri için robots.txt ve kullanım koşulları kontrol edilir.
- **NFR-5 Gecikme:** Bildirim hesabı yaklaşık 5 sn içinde tamamlanır.
- **NFR-6 Genişletilebilirlik:** Yeni veri kaynağı (gerçek OBS, başka şehir) yalnızca yeni bir adapter olarak eklenir.
- **NFR-7 Açıklanabilirlik:** Bildirimde hat ve kalan süre, RAG cevaplarında kaynak bağlantısı gösterilir.
- **NFR-8 Test edilebilirlik:** Bildirim kuralları ve rol filtreleri birim testlerle, RAG cevapları hazırlanacak bir soru setiyle doğrulanır.
- **NFR-9 Güvenlik:** Taranan içerik LLM'e talimat olarak değil veri olarak verilir (prompt injection riski), tool yetkileri kullanıcının rolüyle sınırlanır.

## 7. Mimari

Parçalar ve görevleri:

- **Mobil istemci:** Flutter (önce Android, iOS sonra). FCM ile push, favori durak, ders programı, sohbet ve duyuru ekranı.
- **Backend:** FastAPI. Kullanıcı, ders programı, favori durak ve EGO önbelleği (bellek içi, kısa ömürlü).
- **Veritabanı:** Supabase. PostgreSQL, Auth ve pgvector tek yerde, ayrı vektör veritabanı yok.
- **Zamanlayıcı:** APScheduler. Günlük bildirim işleri ve gece 03:00 kazıyıcı. Celery ve Redis kullanılmaz.
- **Ingest:** Kendi kodumuzla kazıma (RSS, HTML, PDF), parçalama ve embedding. LangChain/LlamaIndex gerekmez.
- **MCP sunucusu:** Python MCP SDK ile EGO, ders programı, favori durak, rol ve doküman arama tool'ları.
- **LLM:** Tek sağlayıcı (OpenAI gpt-4o-mini ya da Groq/Llama-3), yalnızca sohbet için.

Veri akışı: Bildirimler LLM'siz çalışır. Zamanlayıcı ders programına ve EGO verisine bakar, kurala göre FCM ile bildirim gönderir. LLM yalnızca kullanıcı sohbet ettiğinde MCP tool'larıyla çağrılır. Mobil cihaz EGO'ya doğrudan istek atmaz.

Tek repo (monorepo) kullanılır. `main` dalı her zaman çalışır durumda kalır, işler `feat/<modül>-<konu>` dallarında yapılır, her iterasyon sonunda etiket atılır (`v0.1-backend` gibi).

## 8. Haber, bülten ve portal içerikleri (RAG)

1. **Kaynaklar (adım adım):** Başlangıçta 3-5 kaynak: merkezi duyurular, yönetmelikler sayfası, bir fakülte sitesi ve öğrenci işleri. Sonra kaynak sayısı artırılır. Önce RSS, yoksa HTML; PDF'ler metne çevrilir.
2. **Etiket:** Rol ve fakülte etiketi kaynaktan atanır (sayfa Mühendislik Fakültesi'ne aitse etiket buna göre), LLM'e bırakılmaz.
3. **Parçalama ve indeks:** Yönetmelikler madde sınırlarında parçalanır, Türkçe destekli çok dilli embedding ile pgvector'e yazılır. Kaynak adresi ve tarih saklanır.
4. **Sorgu:** Rol ve fakülte filtresi vektör sorgusunda uygulanır.
5. **Cevap:** Asistan en ilgili parçalarla kaynak bağlantılı cevap verir, kaynakta yoksa bulamadığını söyler. "Kesin yanıt" iddia edilmez, doğruluk hazırlanacak bir soru setiyle ölçülür.
6. **Güncelleme:** Gece 03:00 tam tarama, gün içinde RSS kontrolü. Sayfa içeriği önceki taramayla karşılaştırılarak değişiklik algılanır.
7. **Güvenlik:** Taranan metin LLM'e veri olarak verilir, içindeki talimatlar yok sayılır.

**Gelecek çalışmalar.** Gerçek OBS entegrasyonu, tüm Ankara hatları, web istemcisi, konuma dayalı bildirim ve biriken bildirim kayıtlarıyla EGO tahminini düzelten gecikme modeli.

## 9. İterasyon planı

İterasyonlar en düşük riskli dikey dilimle (Senaryo 2) başlar ve altyapıyı uçtan uca doğrular, en riskli parçalar sonra gelir. Her iterasyonun sonunda çalışan bir sürüm bulunur. Dönemler tahminidir, teslim ve savunma tarihi öğrenilince takvim kesinleşecektir.

| İterasyon | Dönem | Çıktı | Kabul kriteri |
|---|---|---|---|
| 0 – Temel | Kasım ilk hafta | Repo, FastAPI iskeleti, Supabase, EGO adapter'ı, mock kullanıcı ve durak verisi | Seçili duraklarda EGO verisi API'den gelir ve EGO Cep ile tutarlıdır |
| 1 – Senaryo 2 (dikey dilim) | Kasım | Flutter (Android) giriş, favori durak, FCM, zamanlayıcı | Gerçek cihazda favori durak bildirimi gelir |
| 2 – Senaryo 1 | Aralık | Ders programı, yürüme süresi tablosu, ders bitişi bildirimi, bildirim kuralları | Gerçek ders gününde bildirim doğru zamanda ve doğru süreyle gelir |
| 3 – RAG ve MCP | Aralık sonu - Ocak | Ingest (3-5 kaynak), pgvector, MCP tool'ları, sohbet ekranı | Soru setinde doğruluk ölçülür |
| 4 – Duyuru akışı | Ocak | Gece kazıyıcı, rol ve fakülte etiketi, "Sana özel duyurular" | Mühendislik öğretim üyesi hesabı yalnızca ilgili duyuruları görür |
| 5 – Pilot ve ölçüm | Şubat | Kaynak sayısını artırma, bildirim logu, gerçek kullanıcı denemesi, düzeltmeler | Pilot geri bildirimi işlenir |
| 6 – Rapor ve sunum | Şubat sonu | Final rapor, demo | Tüm zorunlu gereksinimler kanıtlı |

İsteğe bağlı kalemler (FR-14, FR-15) zaman daralırsa kırpılır, proje yine bütün kalır.

## 10. Riskler ve önlemler

| Risk | Etki | Önlem |
|---|---|---|
| EGO endpoint'i resmi değil, değişebilir veya kapanabilir | Yüksek | Önbellek, son geçerli veri, raporda açık beyan, resmi kaynak (açık veri portalı) için yedek plan |
| Kullanıcı sayısı artınca EGO'ya yük biner | Orta | Durak bazlı paylaşılan sorgu ve 30-45 sn önbellek |
| OBS erişimi alınamaz | Orta | Mock veri ve adapter arayüzü |
| Okul siteleri çok sayıda ve farklı yapıda, taramaya izin vermeyebilir | Yüksek | 3-5 kaynakla başla, RSS öncelikli, robots.txt kontrolü, gerekirse BİDB'den izin |
| RAG yanlış veya eski bilgi verir | Yüksek | Kaynak bağlantısı ve tarih, kaynakta yoksa bulamadığını söyleme, soru seti ile ölçüm |
| Taranan içerikte gizli talimat (prompt injection) | Orta | İçerik veri olarak işaretlenir, tool yetkileri rolle sınırlanır |
| Kapsam büyük, tek kişi | Yüksek | Dikey dilimle başlama, zorunlu/olması gereken/isteğe bağlı ayrımı |
| Bildirimler kullanıcıyı bunaltır | Orta | Tekrar engelleme, sessiz saatler, kapatma seçeneği |
| iOS push için ücretli Apple Developer hesabı gerekir | Orta | Android ile başla, iOS sonra |
| Kişisel veri (KVKK) | Orta | Pilotta mock veri, konum alınmaz, ileride açık rıza |
| LLM maliyeti | Düşük | LLM yalnızca sohbette, küçük model |

## 11. Başarı ölçütleri

- Gerçek cihazda Senaryo 1 ve 2 bildirimleri doğru zamanda ve doğru süreyle gelir.
- Bildirimdeki otobüs süreleri EGO Cep ile tutarlıdır.
- RAG cevapları hazırlanacak soru setinde doğru kaynakla gelir, kaynakta olmayan soruda "bulamadım" denir.
- Rol ve fakülte filtresi testi: bir rolün içeriği başka rolde görünmez.
- Bildirim logu (FR-14) yapılırsa, söylenen süre ile gerçek geliş farkı raporda sayısal olarak verilir.

## 12. Açık sorular

1. Bitirme projesinin teslim ve savunma tarihi nedir?
2. Pilot için Gölbaşı 50. Yıl ve Tandoğan çevresinde hangi duraklar (numaralarıyla) seçilecek?
3. İlk taranacak 3-5 okul kaynağı hangileri ve hangileri giriş gerektiriyor?
4. Backend nerede çalışacak (Supabase yanında bir bulut ya da VPS)?
5. LLM sağlayıcısı OpenAI mı Groq mu, maliyet nasıl karşılanacak?
6. Test cihazı Android mi iOS mu? (Android varsayıldı)
7. Danışmanın veri kaynağı, portal erişimi ve KVKK konusundaki görüşü nedir?

## 13. İlerleme notları

Bu bölüm ajanlar ve geliştirici arasında devir teslim içindir. Her oturum sonunda güncellenir.

- **Son tamamlanan iterasyon:** (henüz yok)
- **Şu an üzerinde çalışılan:** (henüz yok)
- **Kaldığım yer / sıradaki adım:** (henüz yok)
- **Alınan kararlar ve sapmalar:** (henüz yok)

# Devir notu – Akıllı Kampüs Asistanı (4 Kasım 2026)

## Proje
Ankara Üniversitesi bitirme projesi, tek geliştirici. Mobil uygulama (Flutter, önce Android) + FastAPI backend + Supabase (PostgreSQL, Auth, ileride pgvector) + MCP sunucusu + LLM sohbet asistanı. Kullanıcı kendi duraklarını numarayla ekler, sistem ders programına ve EGO canlı otobüs verisine bakıp kural tabanlı bildirim gönderir. Okul duyuruları/yönetmelikleri RAG ile sohbete bağlanır.

Bağlayıcı belge: `akilli-kampus-proje-raporu.md` (gereksinimler FR-1..15, NFR-1..9, 7 iterasyon). Gereksinim numaralarına atıf yap, kapsam dışı maddelere dokunma (web istemcisi, gerçek OBS, konum takibi, tahmin modeli).

## Değişmez kararlar
- Bildirimler LLM kullanmaz, kural tabanlıdır. LLM yalnızca kullanıcı sohbet ettiğinde MCP tool'larıyla çağrılır.
- Mobil cihaz EGO'ya doğrudan istek atmaz, hep backend üzerinden (durak başına 30 sn önbellek).
- Ayrı vektör DB yok (pgvector), Celery/Redis yok (APScheduler), LangChain yok.
- Konum alınmaz. Pilotta mock kullanıcı verisi.
- Rol/fakülte kısıtı RAG'da vektör sorgusunun metadata filtresinde uygulanır, prompt'ta değil.
- `service_role` anahtarı asla istemciye ya da repoya girmez.

## Yapılanlar (iterasyon 0)
Repo yapısı:
```
backend/
  app/ego.py          # EGO adapter: canlı/tarife ayrımı, 30 sn TTL önbellek, hata olursa stale veri
  app/main.py         # FastAPI: GET /, GET /config, GET /stops/{durak_no}/arrivals
  app/static/index.html  # geçici web arayüzü (giriş, durak ekle/sil, canlı araçlar)
  tests/test_ego.py   # 7 test, hepsi geçiyor
  .env.example, requirements.txt, pytest.ini
supabase/schema.sql, seed.sql
tools/                # eski probe betikleri (collector kullanılmıyor)
```
Supabase şeması: `profiles` (rol: ogrenci/akademisyen/idari, fakülte), `favorite_stops` (durak_no, ad, yuruyus_dk boş olabilir, kullanıcı başına en fazla 10 durak tetikleyiciyle), `schedule_items` (gun 1-7, baslangic, bitis). Hepsinde RLS: kullanıcı yalnızca kendi satırını görür.

## EGO servisi hakkında doğrulanmış bilgiler
Endpoint: `https://egocptsrvand.ego.gov.tr/mblSrv14/service.asp?FNC=Otobusler&DURAK=<no>` (resmi olmayan, raporda açıkça belirtilecek). Cevap `{"table":[...],"status":"TRUE"}`.
- Alanlar: `arac_no`, `sure`, `detay`, `hat_kod`, `hat_no`, `hat_kisa_kod`, `hat_ad`.
- Canlı araç: `arac_no` dolu (örn. "07-179"), `sure` "2 dk", "1 sa 5 dk" ya da "Geliyor". Adapter bunları `dakika` (Geliyor = 0) ve `geliyor` alanına çevirir.
- Tarife satırı: `arac_no` "-", `sure` örn. "Sonraki Hareket Saati İlk Duraktan 11:00 / 27 dk Sonra". Bu, hattın İLK durağından kalkış saatidir, bu durağa varış değildir.
- Boş `table` hem geçersiz numara hem "araç yok" demek olabilir, ayırt edilemez (`bos: true`).
- Doğrulandı: çıktı EGO Cep uygulamasıyla tutarlı, durak 12579 çalışıyor. EgoPy'nin eski sunucusu (88.255.141.70) kapalı.

## Rapordan sapmalar (rapor henüz güncellenmedi)
- Kampüs durakları için hazır yürüme süresi tablosu (FR-7) çıkarıldı. `favorite_stops.yuruyus_dk` boş bırakılabilir alan olarak duruyor, Senaryo 1'e gelince varsayılan değer ya da durak başına giriş kararı verilecek.
- Web arayüzü yalnızca geliştirme/test amaçlı, kapsam dışı kalmaya devam ediyor. Asıl istemci Flutter.

## Doğrulanmamış noktalar
- `schema.sql` ve `seed.sql` geliştiricinin Supabase projesinde çalıştırılıp çalıştırılmadığı bilinmiyor. Hata alınırsa mesaj paylaşılacak. Daha önce eski şema çalıştırıldıysa `drop table campus_stops;` gerekir ve tetikleyici ayrıca eklenmelidir.
- `index.html` gerçek bir tarayıcıda ve gerçek Supabase projesiyle henüz denenmedi.
- `/stops/{no}/arrivals` şimdilik kimlik doğrulamasız, dışarı açmadan önce Supabase JWT kontrolü eklenmeli.

## Sıradaki adımlar
1. İterasyon 0'ı kapat: SQL'leri çalıştır, `backend/.env` doldur, `uvicorn app.main:app --reload --env-file .env`, `ogrenci@test.local` ile girişi ve durak eklemeyi doğrula.
2. İterasyon 1 (Senaryo 2, en düşük riskli dikey dilim): Flutter (Android) giriş + favori durak, FCM push, APScheduler ile "ilk dersten ~1 saat önce favori durak kontrolü" ve bildirim kuralları (aynı araç için tekrar yok, sessiz saat, kapatma).
3. Backend'e JWT doğrulaması ekle.
4. MCP sunucusu: geliştiricinin kendi MCP dokümanına göre kurulacak. Tool'lar: `get_ego_live_data` (backend uç noktasını çağırır), `get_schedule`, `get_favorite_stops`, `get_user_role`, `search_university_docs` (sonraki iterasyon).

## Açık sorular
Teslim/savunma tarihi, taranacak ilk 3-5 okul kaynağı ve giriş gerektirenler, backend barındırma yeri, LLM sağlayıcısı (OpenAI/Groq), test cihazı (Android varsayıldı), danışmanın KVKK ve veri kaynağı görüşü, EGO'nun resmi bir durak listesi (ad/konum) olup olmadığı.

## Çalışma kuralları
Her seferinde tek iterasyon. Her adımda çalışan ve test edilmiş bir sürüm bırak, yapılmayan/doğrulanmayan şeyi açıkça yaz. Kapsamı sessizce genişletme, rapordan sapma gerekiyorsa önce sor.
