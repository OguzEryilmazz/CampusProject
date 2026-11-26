# RAG veritabanı (Supabase)

Supabase web panelinden yönetilir; bu dosya **26 Kasım 2026'da panelden alınan** durumun kaydıdır. Panelde bir şey
değişirse burası elle güncellenmelidir.

## Tablolar

**`documents`**: bir kaynak (yönetmelik, Bologna dersi, duyuru)

| Sütun | Tip | Not |
|---|---|---|
| `id` | bigint | PK |
| `kaynak_id` | text, NOT NULL | **benzersiz**. `ingest.py` bunu `kaynak_url`'den (yoksa `dosya:<yol>`) üretir |
| `kaynak_url`, `baslik`, `tur` | text | `tur` NOT NULL |
| `roller` | text[], NOT NULL | boş dizi = herkese açık |
| `fakulte` | text | null = tüm fakülteler |
| `icerik_hash` | text, NOT NULL | değişmeyen kaynak atlanır |
| `yayin_tarihi` | date | |
| `updated_at` | timestamptz | |

**`doc_chunks`**: kaynağın parçaları

| Sütun | Tip | Not |
|---|---|---|
| `id`, `document_id` | bigint | `(document_id, chunk_index)` benzersiz |
| `chunk_index` | integer | |
| `madde` | text, null olabilir | Bologna parçalarında hep null |
| `icerik`, `baslik` | text, NOT NULL | `icerik` başında `baslik` satırı var (`chunk_text` ekler) |
| `embedding` | vector, NOT NULL | boyut: **doğrulanmadı** (README 1536 diyor) |
| `roller` | text[], NOT NULL | belgeden kopyalanır; filtre burada uygulanır |
| `fakulte`, `kaynak_url` | text | |

## İndeksler

- `doc_chunks`: `doc_chunks_pkey`, `doc_chunks_document_id_chunk_index_key` (benzersiz),
  `doc_chunks_embedding_idx` = `hnsw (embedding vector_cosine_ops)`
- `documents`: `documents_pkey`, `documents_kaynak_id_key` (benzersiz)

## Arama fonksiyonu

```sql
CREATE OR REPLACE FUNCTION public.match_chunks(query_embedding vector, match_count integer DEFAULT 5, p_rol text DEFAULT NULL::text, p_fakulte text DEFAULT NULL::text)
 RETURNS TABLE(id bigint, document_id bigint, madde text, icerik text, baslik text, kaynak_url text, score double precision)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'extensions'
AS $function$
  select c.id, c.document_id, c.madde, c.icerik, c.baslik, c.kaynak_url,
         1 - (c.embedding <=> query_embedding) as score
  from doc_chunks c
  where (cardinality(c.roller) = 0 or p_rol = any (c.roller))
    and (c.fakulte is null or c.fakulte = p_fakulte)
  order by c.embedding <=> query_embedding
  limit least(match_count, 20)
$function$
```

## Davranış (fonksiyondan çıkan)

- **`roller = []` herkese açık demektir**; `fakulte = null` tüm fakülteler demektir. Bologna kaynakları böyle yüklenir.
- Profil yoksa `p_rol` null gelir: yalnızca herkese açık (boş roller) parçalar döner.
- **`score` kosinüs benzerliğidir** (1 − kosinüs mesafesi), yüksek = iyi. "Kaynakta yok" eşiği bu ölçekte seçilir.
- En fazla **20** sonuç döner (`match_count` ne olursa olsun).
- Fakülte karşılaştırması **birebir metin eşitliğidir**. Bologna'daki ad ("Mühendislik Fakültesi") ile
  `profiles.fakulte` değeri farklı yazılıyorsa fakülteye özel bir kaynak eşleşmez; şimdilik Bologna `fakulte = null` yüklendiği için sorun yok.
- Filtre (`where`) HNSW indeksinin üstünde uygulanır; filtre çoksa dönen sonuç `k`'dan az olabilir. Külliyat büyüyünce `rag_eval` ile ölçülmeli.
- Aramada `tur` filtresi yok (örn. yalnızca yönetmelik ya da yalnızca Bologna). Gerekirse fonksiyona parametre eklemek gerekir.
