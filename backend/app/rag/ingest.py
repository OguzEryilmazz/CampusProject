"""Kaynak dosyaları okuyup parçalar, vektörler ve veritabanına yazar.

Kullanım (backend klasöründen):  python -m app.rag.ingest [--config data/kaynaklar.json]
Değişmeyen kaynaklar atlanır (içerik + metadata özeti ile karşılaştırılır).
"""
import argparse
import asyncio
import hashlib
import json
import logging
import os
from html.parser import HTMLParser
from pathlib import Path

from .chunking import chunk_text

log = logging.getLogger("ingest")
_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "article"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html):
    p = _Text()
    p.feed(html)
    return "".join(p.parts)


def read_source(path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    if ext in (".html", ".htm"):
        return html_to_text(path.read_text(encoding="utf-8"))
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    raise ValueError(f"Desteklenmeyen dosya türü: {ext}")


def _vec(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


async def ingest_source(db, embedder, entry, base_dir="."):
    """Tek kaynağı işler. 'atlandi' | 'yazildi' | 'bos' döner."""
    path = Path(base_dir) / entry["dosya"]
    text = read_source(path)
    meta = {
        "baslik": entry["baslik"], "tur": entry.get("tur", "duyuru"),
        "roller": sorted(entry.get("roller", [])), "fakulte": entry.get("fakulte"),
        "kaynak_url": entry.get("kaynak_url"), "yayin_tarihi": entry.get("yayin_tarihi"),
        "embedder": getattr(embedder, "model_id", ""),   # sağlayıcı/model değişirse yeniden vektörlenir
    }
    digest = hashlib.sha256(json.dumps({"t": text, "m": meta}, sort_keys=True).encode()).hexdigest()
    kaynak_id = entry.get("kaynak_url") or f"dosya:{entry['dosya']}"

    mevcut = await db.get_document(kaynak_id)
    if mevcut and mevcut["icerik_hash"] == digest:
        return "atlandi"

    parcalar = chunk_text(text, meta["baslik"])
    if not parcalar:
        return "bos"
    vektorler = await embedder.embed([p["icerik"] for p in parcalar], kind="document")  # önce vektörle, sonra eskiyi sil

    doc_id = await db.upsert_document({
        "kaynak_id": kaynak_id, "kaynak_url": meta["kaynak_url"], "baslik": meta["baslik"],
        "tur": meta["tur"], "roller": meta["roller"], "fakulte": meta["fakulte"],
        "yayin_tarihi": meta["yayin_tarihi"], "icerik_hash": digest,
    })
    if mevcut:  # yeni doküman değilse eski parçaları sil
        await db.delete_chunks(doc_id)
    await db.insert_chunks([{
        "document_id": doc_id, "chunk_index": i, "madde": p["madde"], "icerik": p["icerik"],
        "embedding": _vec(v), "roller": meta["roller"], "fakulte": meta["fakulte"],
        "baslik": meta["baslik"], "kaynak_url": meta["kaynak_url"],
    } for i, (p, v) in enumerate(zip(parcalar, vektorler))])
    log.info("  %s: %d parça yazıldı", meta["baslik"], len(parcalar))
    return "yazildi"


async def ingest_all(db, embedder, config_path):
    config_path = Path(config_path)
    entries = json.loads(config_path.read_text(encoding="utf-8"))
    sonuc = {}
    for e in entries:
        try:
            sonuc[e["baslik"]] = await ingest_source(db, embedder, e, base_dir=config_path.parent.parent)
        except Exception as ex:  # bir kaynak bozuksa diğerleri devam etsin
            log.error("  %s: HATA %s", e.get("baslik"), ex)
            sonuc[e.get("baslik", "?")] = f"hata: {ex}"
    return sonuc


def main():
    from dotenv import load_dotenv

    from ..config import service_role_key, supabase_url
    from ..db import Db
    from .embeddings import make_embedder

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="data/kaynaklar.json")
    args = ap.parse_args()

    url, key, embedder = supabase_url(), service_role_key(), make_embedder()
    if not (url and key):
        raise SystemExit("SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY .env içinde dolu olmalı")
    if embedder is None:
        raise SystemExit("GEMINI_API_KEY (ya da OPENAI_API_KEY) .env içinde dolu olmalı")
    print(f"Vektörleme: {embedder.model_id}")
    sonuc = asyncio.run(ingest_all(Db(url, key), embedder, args.config))
    for baslik, durum in sonuc.items():
        print(f"{durum:10} {baslik}")


if __name__ == "__main__":
    main()