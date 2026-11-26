"""RAG değerlendirme aracı.

Kullanım (backend klasöründen):
    python -m rag_eval.runner                          # örnek soru setiyle
    python -m rag_eval.runner --sorular rag_eval/sorular.json --rol ogrenci --fakulte Mühendislik

Gerçek Supabase ve gömme servisini kullanır (.env gerekir). Sonuçlar rag_eval/sonuclar/ altına
JSON ve Markdown olarak yazılır. Uygulama koduna dokunmaz, yalnızca app.rag.search'ü çağırır.
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from .metrics import build_record, load_questions, markdown_report, summarize


async def run_eval(sorular, search_fn, k=5, bekleme=0.0):
    """search_fn(soru, rol, fakulte, k) -> [{'baslik','madde','score',...}] (async)."""
    records = []
    for q in sorular:
        try:
            hits = await search_fn(q["soru"], q.get("rol"), q.get("fakulte"), k)
            records.append(build_record(q, hits))
        except Exception as e:  # tek soru hata verirse ölçüm devam etsin
            records.append({"soru": q["soru"], "tur": q["tur"], "grup": q.get("grup"), "hata": str(e)[:300]})
        if bekleme:
            await asyncio.sleep(bekleme)
    return records


def write_outputs(out_dir, meta, records, summary):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ad = datetime.now().strftime("%Y%m%d-%H%M%S")
    (out_dir / f"{ad}.json").write_text(
        json.dumps({"meta": meta, "ozet": summary, "kayitlar": records}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    rapor = markdown_report(meta, records, summary)
    (out_dir / f"{ad}.md").write_text(rapor, encoding="utf-8")
    return out_dir / f"{ad}.md", rapor


def main():
    from dotenv import load_dotenv

    from app.config import service_role_key, supabase_url
    from app.db import Db
    from app.rag.embeddings import make_embedder
    from app.rag.search import search

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sorular", default="rag_eval/sorular.ornek.json")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--rol", default="ogrenci")
    ap.add_argument("--fakulte", default="Mühendislik")
    ap.add_argument("--bekleme", type=float, default=0.7,
                    help="sorular arası saniye (ücretsiz Gemini katmanında dakikada ~100 istek sınırı için)")
    ap.add_argument("--cikti", default="rag_eval/sonuclar")
    a = ap.parse_args()

    url, key, embedder = supabase_url(), service_role_key(), make_embedder()
    if not (url and key):
        raise SystemExit("SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY .env içinde dolu olmalı")
    if embedder is None:
        raise SystemExit("GEMINI_API_KEY (ya da OPENAI_API_KEY) .env içinde dolu olmalı")

    sorular = load_questions(a.sorular)
    db = Db(url, key)

    async def search_fn(soru, rol, fakulte, k):
        return await search(db, embedder, soru, rol or a.rol, fakulte if fakulte is not None else a.fakulte, k)

    print(f"{len(sorular)} soru, vektörleme: {embedder.model_id}")
    records = asyncio.run(run_eval(sorular, search_fn, a.k, a.bekleme))
    summary = summarize(records)
    meta = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "model_id": embedder.model_id,
            "rol": a.rol, "fakulte": a.fakulte, "k": a.k, "soru_dosyasi": a.sorular}
    yol, rapor = write_outputs(a.cikti, meta, records, summary)
    print(rapor)
    print(f"\nKaydedildi: {yol}")


if __name__ == "__main__":
    main()
