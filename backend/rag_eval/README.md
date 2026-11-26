# RAG değerlendirme aracı

RAG aramasının ne kadar doğru çalıştığını ölçer ve "kaynakta yok, bulamadım" eşiğini veriyle seçmeye yarar.
Uygulama koduna dokunmaz, yalnızca `app.rag.search`'ü çağırır. Rapor ve bitirme raporu için sayısal sonuç üretir.

## Çalıştırma

```powershell
cd backend
python -m rag_eval.runner                                    # örnek soru setiyle (araç denemesi)
python -m rag_eval.runner --sorular rag_eval/sorular.json    # gerçek soru setiyle
```

İsteğe bağlı: `--rol ogrenci --fakulte Mühendislik --k 5 --bekleme 0.7`. Gerçek Supabase ve gömme
servisi (`GEMINI_API_KEY` ya da `OPENAI_API_KEY`) gerekir. Sonuçlar `rag_eval/sonuclar/` altına
`.md` (okunur rapor) ve `.json` (ayrıntı) olarak yazılır. Ücretsiz Gemini katmanında dakikada yaklaşık
100 istek sınırı olduğu için sorular arasında varsayılan 0,7 sn beklenir.

## Soru seti (`rag_eval/sorular.json`)

Liste halinde JSON. Biçim için `sorular.ornek.json` dosyasına bak (o dosya yalnızca uydurma örnek metin içindir).

```json
{"soru": "mazeret sınavı için kaç gün içinde başvurulur", "tur": "ilgili",
 "beklenen": [{"baslik": "Eğitim-Öğretim Yönetmeliği", "madde": "Madde 25"}]}

{"soru": "yemekhane hafta sonu açık mı", "tur": "alakasiz", "grup": "alan_ici_yok"}
```

- **`ilgili`:** Cevabı külliyatta olan soru. `beklenen` listesinde doğru sayılacak kaynak/madde yazılır.
  `baslik` içerme ile, `madde` eşitlik ile karşılaştırılır (Türkçe harf ve büyük/küçük harf farkı önemsenmez).
  Cevap birden fazla maddeye yayılıyorsa hepsini listele, herhangi biri bulunursa doğru sayılır.
- **`alakasiz`:** Cevabı külliyatta **olmayan** soru. Sistemin "bulamadım" demesi gerekir.
  `grup: tamamen_alakasiz` (hava durumu, tarif) ya da `grup: alan_ici_yok` (okulla ilgili ama dokümanlarda
  cevabı yok, asıl zor olan bu).
- İstersen soruya özel `"rol"` ve `"fakulte"` yazılabilir (yoksa komut satırındaki değerler kullanılır).

### Soru yazarken

- En az **20 ilgili, 10 alakasız** soru. Hedef 30 ilgili, 15 alakasız (8 tamamen alakasız, 7 alan içi yok).
  Daha azıyla rapor "eşik güvenilir değil" uyarısı verir.
- Her kaynak için en az 3 ilgili soru. Aynı bilgiyi farklı biçimde sor: resmi dil, günlük dil, kısa, yazım hatalı.
- Soruları **parçaya bakarak değil, bir öğrencinin soracağı gibi** yaz. Yoksa sonuç olduğundan iyi çıkar.
- `alan_ici_yok` sorularının cevabının külliyatta gerçekten olmadığından emin ol. Sonradan eklenen bir doküman
  cevabı veriyorsa o soruyu çıkar ya da `ilgili`ye çevir.
- Soruların yaklaşık beşte birini eşik seçerken **kullanma**, eşiği seçtikten sonra ayrı bir dosyayla doğrula.

## Raporu okuma

| Ölçüt | Anlamı |
|---|---|
| top-1 | İlgili soruların kaçında ilk sonuç doğru kaynak |
| top-k | Doğru kaynak ilk k sonuç içinde |
| MRR | Doğru kaynağın sırasına göre ortalama (1,0 = hep ilk) |
| Alakasız skor dağılımı | Alakasız sorulara bile verilen en yüksek benzerlik skoru |
| En iyi ayıran eşik | İlgilileri cevaplayıp alakasızları reddetmeyi en iyi dengeleyen skor |
| Güvenli eşik | Alakasızların hiçbirinin geçmediği en düşük skor |

Önerilen kullanım: **güvenli eşiğin üstü** kaynakla cevapla, **ikisi arası** "kesin bir kaynak bulamadım, en
yakın olabilecek şu" de, **altı** "bulamadım" de. Eşik gömme modeline ve boyuta özeldir: sağlayıcı, model,
parçalama ya da kaynak seti değişince yeniden ölç. Rapordaki "doğru kaynağı ilk sırada getirmeyen" soruların
listesi, parçalamayı ve kaynak kalitesini iyileştirmek için en iyi ipucudur.

## Testler

`python -m pytest tests/test_rag_eval.py` (ağ gerektirmez, sahte arama kullanır).
