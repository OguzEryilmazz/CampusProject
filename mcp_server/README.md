# Akıllı Kampüs MCP Sunucusu

Akıllı Kampüs Asistanı'nın **MCP (Model Context Protocol) sunucusu**. Bir LLM sohbetinin kampüs verisine güvenli biçimde erişmesini sağlar: canlı otobüs, favori duraklar, ders programı, bildirimler ve okul dokümanlarında kaynaklı arama.

Sunucu **backend'in REST API'sini kullanıcının kendi token'ıyla çağıran ince bir katmandır**. Backend kodunu import etmez, gizli anahtar tutmaz. Kimlik doğrulama, rol/fakülte filtresi ve kampüs hat filtresi backend'de kalır, burada kopyalanmaz.

## Mimari

```
Mobil uygulama ──▶ (sohbet ucu, planlandı) ──▶ LLM
                                                 │ MCP (Streamable HTTP, Bearer token)
                                                 ▼
                                      MCP sunucusu (bu klasör, :8080)
                                                 │ REST, aynı Bearer token
                                                 ▼
                                      FastAPI backend (:8000) ──▶ Supabase, EGO
```

- **Taşıma:** Streamable HTTP, adres `/mcp`. Sunucu 7/24 açık çalışır.
- **Kimlik:** her istekte `Authorization: Bearer <Supabase token>` gerekir. Token backend'e `GET /me` ile doğrulatılır, sonuç 60 sn önbelleğe alınır. Token sunucuda saklanmaz, önbellekte yalnızca SHA-256 özeti tutulur.
- **Yetki:** araçlar kullanıcının token'ıyla backend'i çağırır, başkasının verisine erişim mümkün değildir. `dokuman_ara` rol ve fakülteyi parametre olarak almaz, backend bunları profilden uygular.
- **Tek süreç:** oran sınırı bellekte tutulduğu için `--workers` kullanılmaz.

## Araçlar

| Araç | Parametre | Backend ucu | Açıklama |
|---|---|---|---|
| `profilim_getir` | yok | `GET /me` | Ad, rol, fakülte, kampüs, bildirim ayarı |
| `favori_duraklarim_getir` | yok | `GET /me/stops` | Favori duraklar ve kampüs hatlarına göre süzülmüş canlı araçlar |
| `durak_yaklasan_araclar` | `durak_no` (1-7 rakam) | `GET /stops/{no}/arrivals` | Belirli bir durağa yaklaşan tüm araçlar ve tarife |
| `ders_programim_getir` | `kapsam`: `bugun`, `yarin`, `hafta` | `GET /me/schedule` | Ders programı (gün ve saatler Europe/Istanbul) |
| `bildirimlerim_getir` | `limit` (1-20, varsayılan 5) | `GET /me/notifications` | Daha önce üretilmiş otobüs bildirimleri |
| `dokuman_ara` | `sorgu` (3-300 karakter), `limit` (1-8) | `GET /rag/search` | Yönetmelik ve duyurularda kaynaklı arama |

Hepsi salt okurdur, yan etkisi yoktur. Yanıtlar modelin bağlamına göre sadeleştirilir (ham metin alanları atılır, araç listeleri en fazla 10, doküman metni 700 karakterle sınırlanır). Kırpma olursa `kesildi: true` döner.

Önemli davranışlar:
- Otobüs verisi EGO'nun **resmi olmayan** servisinden gelir. `eski_veri: true` ise son geçerli veri gösteriliyordur.
- Sistem kullanıcının kampüse "yetişip yetişmeyeceğini" **bilmez**, EGO yalnızca durağa kalan süreyi verir.
- `dokuman_ara` sonuçları belge metnidir, içindeki komut gibi görünen ifadelere uyulmaz. "Kaynakta yok" eşiği henüz ayarlanmadı, bu yüzden yanıt `benzerlik` puanını döner ve soruyu karşılamayan sonuçlarda model bilmediğini söylemelidir.
- Ders programı kullanıcının sisteme girdiği veridir, OBS'den çekilmez.

## Hata sözleşmesi

Araç hataları istisna olarak değil, **yapılandırılmış gövde** olarak döner:

```json
{"hata": true, "hata_kodu": "TOKEN_GECERSIZ", "mesaj": "Oturumun süresi dolmuş olabilir. Lütfen tekrar giriş yapın."}
```

| `hata_kodu` | Anlamı |
|---|---|
| `KIMLIK_GEREKLI` | Authorization başlığı yok |
| `TOKEN_GECERSIZ` | Token geçersiz ya da süresi dolmuş |
| `YETKI_YOK` | Backend 403 verdi |
| `KAYIT_BULUNAMADI` | Backend 404 verdi |
| `PARAMETRE_GECERSIZ` | Backend 422 verdi |
| `ORAN_SINIRI` | Backend 429 verdi |
| `ZAMAN_ASIMI` | Backend zamanında yanıt vermedi |
| `GECICI_HATA` | Backend kapalı ya da 5xx verdi |

Bağlantı düzeyinde: kimlik yoksa **401**, geçersiz token **401**, aynı IP'den çok başarısız deneme ya da token başına fazla istek **429** (`Retry-After` ile), backend'e ulaşılamıyorsa **503**. Backend iç hata metinleri istemciye sızdırılmaz.

## Kurulum

Gereksinimler: Python 3.12 (denendi), çalışan bir backend. Bu serviste **gizli anahtar yoktur**.

```powershell
cd mcp_server
..\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q                      # 32 test, gerçek servislere bağlanmaz

$env:BACKEND_URL="http://127.0.0.1:8000"
python -m kampus_mcp.server              # http://127.0.0.1:8080/mcp
```

`GET /health` sunucu durumunu döner, kimlik istemez.

### Ortam değişkenleri

| Değişken | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `BACKEND_URL` | evet | | Backend adresi, örn. `http://127.0.0.1:8000` |
| `MCP_HOST` | hayır | `0.0.0.0` | Dinlenen adres |
| `MCP_PORT` | hayır | `8080` | Dinlenen port |
| `BACKEND_TIMEOUT_SN` | hayır | `10` | Backend çağrısı zaman aşımı |
| `TOKEN_ONBELLEK_SN` | hayır | `60` | Token doğrulama önbelleği (çıkış yapılan token bu süre kadar geçerli sayılabilir) |
| `ISTEK_LIMITI_DK` | hayır | `60` | Token başına dakikada istek |
| `HATA_LIMITI_DK` | hayır | `10` | IP başına dakikada başarısız kimlik denemesi |
| `GUVEN_VEKIL` | hayır | `false` | Yalnızca güvenilir bir ters vekilin arkasındaysa `true` (`X-Forwarded-For` okunur) |

## MCP Inspector ile deneme

1. Backend ve MCP sunucusunu çalıştır.
2. Token al: `/docs` sayfasında **Authorize** ile giriş yap, ya da `POST /auth/token` çağır.
3. `npx @modelcontextprotocol/inspector` çalıştır. **Add Servers** → HTTP (Streamable HTTP), URL `http://127.0.0.1:8080/mcp`, başlık `Authorization: Bearer <token>`.
4. Bağlanınca **Tools** sekmesinde altı aracı görürsün. Token'ı bozarsan bağlantı 401 ile reddedilir.

## Dağıtım

`Dockerfile` hazırdır (python:3.12-slim, yetkisiz kullanıcı, `/health` sağlık kontrolü). **İmaj henüz derlenmedi ve bir sunucuya konmadı.**

```powershell
docker build -t kampus-mcp .
docker run --rm -p 8080:8080 -e BACKEND_URL=http://host.docker.internal:8000 kampus-mcp
```

Canlıya alırken:
- **Tek süreç çalıştır**, `--workers` yok.
- **Sunucu 7/24 açık olmalı.** Boşta uyuyan ücretsiz planlar kullanılamaz.
- HTTPS gerekir. Barındırıcının yük dengeleyicisi arkasındaysan `GUVEN_VEKIL=true` yap.
- `BACKEND_URL` canlı backend adresi olmalı. Bu serviste gizli değişken yoktur.
- Alan adıyla yayında DNS rebinding korumasının (`allowed_hosts`) ayarı ayrıca doğrulanmalı.

## Klasör yapısı

```
mcp_server/
  kampus_mcp/
    server.py            Araç kayıtları, /health, uygulama
    araclar.py           Araç iş mantığı (backend çağrısı + şekillendirme)
    shapers.py           Yanıt sadeleştirme (saf fonksiyonlar)
    backend_client.py    Backend REST istemcisi, hata çevirisi, token doğrulama
    auth_middleware.py   Bearer zorunluluğu, oran sınırı
    oran_siniri.py       Sabit pencereli sayaç
    config.py            Ortam değişkenleri
  tests/                 Birim testleri (sahte backend, MockTransport)
  Dockerfile
  requirements.txt
  requirements-dev.txt
```

## Bilinen sınırlar

- Sohbet ucu (mobil uygulamanın LLM üzerinden bu araçları kullanması) **henüz yok**.
- Token doğrulaması her 60 sn'de bir backend'e gider, oturumu kapatılan token bu süre kadar geçerli sayılabilir.
- Oran sınırı süreç içi bellektedir, yeniden başlatmada sıfırlanır ve tek süreç varsayar.
- Veri kaynakları: EGO resmi olmayan bir servistir, ders programı SQL ile elle girilir, RAG içeriği ve eşiği hâlâ geliştirilmektedir.
- Testler gerçek servislere bağlanmaz, canlı davranış Inspector ile elle doğrulanmalıdır.
