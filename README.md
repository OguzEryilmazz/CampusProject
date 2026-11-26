# Akıllı Kampüs Asistanı

Ankara Üniversitesi Yazılım Mühendisliği bitirme projesi. Öğrenci ve personelin kampüse ulaşımını ve okul bilgisine erişimini kolaylaştıran bir mobil uygulama ve backend.

- **Canlı otobüs bildirimi:** Kullanıcı favori durağını ekler. Sistem ders programına ve EGO'nun canlı otobüs verisine bakar, otobüs durağa kullanıcının seçtiği süre (5–30 dk) kala yaklaşan otobüsleri **tek bildirimde** listeler. Bildirim kararı **LLM'siz, kural tabanlıdır**.
- **Okul dokümanlarında kaynaklı arama (RAG):** Yönetmelik ve duyurular parçalanıp vektörlenir, kullanıcının rolüne ve fakültesine göre filtrelenerek aranır. Her sonuç kaynağını gösterir.
- **MCP sunucusu ve LLM sohbeti:** Planlandı, henüz yapılmadı.

> Bu proje bir bitirme çalışmasıdır. Otobüs verisi EGO'nun **resmi olmayan** servisinden alınır, bu yüzden bir gün değişebilir ya da kapanabilir.

## Durum

| Bileşen | Durum |
|---|---|
| EGO canlı veri adaptörü | Çalışıyor, EGO Cep ile karşılaştırılarak doğrulandı |
| Giriş doğrulama (Supabase JWT) | Çalışıyor |
| Kural tabanlı bildirim üretimi | Gerçek Supabase ve EGO ile çalıştığı görüldü; bildirimler `notifications` tablosuna kaydediliyor |
| Belgeli REST API (`/docs`) | Yazıldı, testlerle doğrulandı (89 test) |
| Flutter (Android) uygulaması | Telefonda giriş ve favori durak listesi çalışıyor. Durak ekleme, canlı araçlar ve push henüz yok |
| FCM ile gerçek push | Backend tarafı yazıldı ve sahte servislerle test edildi. **Gerçek telefonda denenmedi** |
| RAG hattı | Yazıldı ve sahte servislerle test edildi. **Gerçek embedding servisi ve gerçek belgelerle denenmedi** (anahtar bekleniyor) |
| MCP sunucusu | Yapılmadı |
| Canlı (internete açık) sunucu | Yapılmadı. `Dockerfile` hazır ama imaj derlenmedi |

## Mimari

```
 Flutter (Android) ──HTTPS──▶ FastAPI backend ──▶ Supabase (PostgreSQL, Auth, pgvector)
        ▲                        │   │
        │ push                   │   └──▶ EGO canlı otobüs servisi (resmi olmayan)
        └──── Firebase FCM ◀─────┘
                                 └──▶ Gemini / OpenAI (embedding, yalnızca RAG)
```

- **Backend** (`backend/`): FastAPI. İçinde APScheduler ile her dakika çalışan bildirim zamanlayıcısı vardır.
- **Veritabanı** (`supabase/`): PostgreSQL, Supabase Auth, satır düzeyinde güvenlik (RLS) ve pgvector.
- **Mobil** (`mobile/`): Flutter. Supabase adresini ve anon anahtarı backend'in `/config` uç noktasından alır, uygulamaya gömülü değildir.

## Klasör yapısı

```
backend/
  app/
    main.py          API uç noktaları ve uygulama başlatma
    schemas.py       Yanıt modelleri (/docs örnekleri buradan)
    auth.py          Supabase JWT doğrulama, şifreyle giriş
    ego.py           EGO adaptörü (30 sn önbellek, hatada son geçerli veri)
    rules.py         Bildirim kuralları (saf fonksiyonlar)
    scheduler.py     Bildirim turu (her dakika)
    push.py          FCM HTTP v1 gönderimi
    db.py            Supabase PostgREST istemcisi (service_role)
    rag/             Parçalama, vektörleme, kaynak okuma, arama
    static/          Geliştirme için basit web test sayfası
  data/              RAG kaynak listesi ve örnek metin
  tests/             89 test
  Dockerfile
mobile/              Flutter uygulaması
supabase/            SQL dosyaları
tools/               İlk denemelerde kullanılan EGO test betikleri
```

## Kurulum

### 1. Supabase
SQL Editor'da şu sırayla çalıştır:
`schema.sql` → `seed.sql` → `002_bildirimler.sql` → `003_kampus_hatlari.sql` → `004_bildirim_ayarlari.sql` → `005_cihaz_tokenlari.sql` → `006_rag.sql`.

`seed.sql` öncesinde Authentication > Users bölümünden `ogrenci@test.local`, `akademisyen@test.local`, `idari@test.local` kullanıcılarını (Auto Confirm) oluştur. `test_ders_ekle.sql`, bildirimi denemek için bugüne 20 dk sonra başlayan bir ders ekler.

### 2. Ortam değişkenleri (`backend/.env`)

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `SUPABASE_URL` | evet | `https://PROJE_ID.supabase.co` (yol eklenmez) |
| `SUPABASE_ANON_KEY` | evet | Public / publishable anahtar |
| `SUPABASE_SERVICE_ROLE_KEY` | zamanlayıcı için | **Gizli.** RLS'yi aşar, yalnızca backend'de durur |
| `FIREBASE_SERVICE_ACCOUNT_FILE` | push için | Hizmet hesabı JSON dosyasının yolu. **Gizli**, repoya girmez |
| `GEMINI_API_KEY` | RAG için | Google AI Studio anahtarı (`gemini-embedding-001`, 1536 boyut). İkisi de yoksa RAG kapalı |
| `OPENAI_API_KEY` | RAG için (alternatif) | OpenAI embedding (`text-embedding-3-small`) |
| `EMBEDDING_PROVIDER` | hayır | `gemini` ya da `openai`. Belirtilmezse dolu olan anahtara göre seçilir, ikisi de doluysa Gemini |
| `EMBEDDING_MODEL` | hayır | Sağlayıcının varsayılan modelini değiştirir |

`.env` dosyası yalnızca açılışta okunur, değişince sunucuyu yeniden başlat. Hiçbir gizli anahtar repoya girmemeli (`.gitignore` içinde `.env` olmalı).

### 3. Backend'i çalıştır

```powershell
cd backend
python -m venv ..\.venv        # ilk seferde
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest               # 89 test
uvicorn app.main:app --reload --env-file .env
```

Açılışta hangi bileşenlerin açık olduğu log'da yazar (zamanlayıcı, push, RAG). Tarayıcıda:
- `http://127.0.0.1:8000/docs` → **API dokümantasyonu ve deneme sayfası**
- `http://127.0.0.1:8000/` → basit web test sayfası (geliştirme aracı)
- `http://127.0.0.1:8000/health` → sunucu durumu

### 4. Mobil uygulama (Android)

Telefonda USB hata ayıklama açık olmalı.

```powershell
cd mobile
flutter pub get
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
flutter run
```

`adb reverse`, telefondaki `localhost:8000` adresini bilgisayardaki backend'e bağlar. USB bağlantısı koparsa yeniden çalıştırılmalıdır. Debug sürümünde `http://localhost` için `android/app/src/debug/AndroidManifest.xml` içinde `usesCleartextTraffic="true"` vardır, yayın sürümünü etkilemez.

## API

Tüm uç noktalar ve örnek yanıtlar **`/docs`** sayfasındadır. Sağ üstteki **Authorize** ile e-posta ve şifre girilir, ardından her uç nokta **Try it out** ile denenir.

| Yöntem | Yol | Giriş | Açıklama |
|---|---|---|---|
| GET | `/health` | hayır | Sunucu durumu, hangi bileşenler açık |
| GET | `/config` | hayır | Supabase adresi ve anon anahtar |
| POST | `/auth/token` | hayır | E-posta ve şifreyle giriş (`/docs` denemesi için) |
| GET | `/me` | evet | Profilim (rol, fakülte, kampüs) |
| GET | `/me/stops` | evet | Favori duraklarım ve kampüs hatlarına göre filtrelenmiş canlı araçlar |
| GET | `/me/notifications` | evet | Son bildirimlerim |
| GET | `/stops/{durak_no}/arrivals` | evet | Bir durağa yaklaşan tüm araçlar (ham) |
| POST | `/devices` | evet | Telefonun FCM token'ını kaydet |
| DELETE | `/devices/{token}` | evet | Cihaz kaydını sil |
| GET | `/rag/search?q=` | evet | Dokümanlarda arama (rol ve fakülte profilden) |

## Bildirim mantığı (Senaryo: okula geliş)

Her dakika çalışan zamanlayıcı şunu yapar:

1. Bugün dersi olan kullanıcıları bulur. Günün **ilk dersine 60 dk kala** pencere açılır, ders başlayınca kapanır.
2. Kullanıcının kampüsüne (`profiles.kampus`) hizmet veren hatları `campus_lines` tablosundan alır. Hatları kullanıcı değil biz tanımlarız.
3. Favori duraklarda bu hatlardan, kullanıcının o durak için seçtiği süre (`bildirim_dk`) içindeki **tüm** canlı araçları toplar.
4. Listede daha önce bildirilmemiş en az bir araç varsa **tek bildirimde** hepsini yazar: *"Saat 09:00 dersin için Ev durağına yaklaşan otobüsler: 114-1 (5 dk), 115-1 (10 dk)."*
5. Bildirimi `notifications` tablosuna kaydeder, push açıksa kullanıcının cihazlarına gönderir.

Bildirilen araç 60 dk boyunca yeniden bildirilmez. EGO verisi eskiyse ya da kullanıcı bildirimleri kapattıysa bildirim üretilmez. Sistem "yetişirsin" ya da "geç kalırsın" **demez**, çünkü EGO durağa kalan süreyi verir, kampüse varış süresini vermez.

## Güvenlik notları

- Her tabloda RLS açık. Kullanıcı yalnızca kendi satırını görür. `notifications` ve `device_tokens` tablolarına yalnızca backend yazar.
- Kullanıcı profilinde yalnızca `bildirim_acik` alanını değiştirebilir. Rol, fakülte ve kampüs değiştirilemez, çünkü RAG erişimi bunlara göre belirlenir.
- RAG'da rol ve fakülte filtresi vektör sorgusunun içinde (SQL fonksiyonu) uygulanır, istemciden alınmaz.
- `/config` anon anahtarı herkese açar. Bu tasarım gereğidir, yetki RLS ile sağlanır.
- `/auth/token` Supabase girişine aracılık eder. Herkese açık bir sunucuda istek sınırlaması eklenmelidir, şu an yoktur.
- `/stops/{no}/arrivals` ve diğer uç noktalar giriş ister.

## Dağıtım (canlı sunucu)

`backend/Dockerfile` hazır ama **derlenmedi ve bir sunucuya konmadı**. Dikkat edilecekler:

- **Tek süreç çalıştır** (`--workers` yok). Zamanlayıcı uygulamanın içindedir, birden çok süreç aynı bildirimi tekrar üretir.
- **Sunucu 7/24 açık olmalı.** Boşta uyuyan ücretsiz planlar bildirimleri kaçırır.
- Ortam değişkenleri barındırıcının gizli değişken bölümüne girilir, imaja gömülmez. Firebase JSON dosyası için barındırıcının dosya/gizli ayarı kullanılır.
- HTTPS gerekir, mobil uygulamanın yayın sürümü düz `http` kullanamaz.
- Mobil uygulamada `API_BASE` değişkeni canlı adrese çevrilir: `flutter run --dart-define=API_BASE=https://...`

## Bilinen sınırlar

- EGO servisi resmi dokümantasyonu olmayan bir uç noktadır. Boş cevap, geçersiz numara ile "araç yok" arasında ayırt edemez.
- `campus_lines` başlangıç listesi (`114-1`, `115-1`, `115-4`) hat adında "KAMPÜS" geçmesine dayanıyor, gerçek güzergâhlarla doğrulanmadı.
- Ders programı şimdilik SQL ile giriliyor, uygulamada ekranı yok.
- Pilot kapsamı: Gölbaşı 50. Yıl ve Tandoğan. Gerçek OBS yerine sahte kullanıcı ve ders verisi.
- RAG için "kaynakta yok" eşiği henüz ayarlanmadı, gerçek belgelerle soru seti hazırlanınca ayarlanacak.

## Yol haritası

- **8 Ocak 2027, 23:59:** Ara/Tasarım raporu ve sunumu
- **Önce:** FCM push'un gerçek telefonda denenmesi, uygulamada durak ekleme ve canlı araçlar, RAG'ın gerçek belgelerle denenmesi, canlı sunucu
- **Bahar dönemi:** MCP sunucusu ve LLM asistanı, duyuru taraması, pilot ve değerlendirme, poster, video ve final raporu

## Testler

```powershell
cd backend
python -m pytest
```

Testler gerçek servislere bağlanmaz, EGO, Supabase, FCM ve OpenAI sahte servislerle değiştirilmiştir. Bu yüzden gerçek servislerle çalışma ayrıca elle denenmelidir.