"""Metin -> vektör. Sağlayıcı .env ile seçilir: Gemini (varsayılan, anahtar varsa) ya da OpenAI.

Şemadaki vektör boyutu 1536'dır (supabase/006_rag.sql). Her iki sağlayıcı da 1536 boyut üretir.
Sağlayıcı değişirse vektör uzayı değişir: kaynaklar yeniden vektörlenmelidir. Bu, `model_id`
özetin içinde olduğu için `python -m app.rag.ingest` tarafından otomatik yapılır.
"""
import asyncio
import os

import httpx

DIMENSIONS = 1536
OPENAI_URL = "https://api.openai.com/v1/embeddings"
OPENAI_DEFAULT_MODEL = "text-embedding-3-small"
GEMINI_DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_MODEL = OPENAI_DEFAULT_MODEL   # geriye dönük uyum


class EmbeddingError(Exception):
    pass


class OpenAIEmbedder:
    def __init__(self, api_key, model=OPENAI_DEFAULT_MODEL, http=None, batch=64):
        self._key, self._model, self._batch = api_key, model, batch
        self._http = http or httpx.AsyncClient(timeout=60)
        self.model_id = f"openai:{model}"

    async def embed(self, texts, kind="document"):
        """Metin listesi -> aynı sırada vektör listesi. (OpenAI'de belge/sorgu ayrımı yok.)"""
        out = []
        for i in range(0, len(texts), self._batch):
            part = texts[i:i + self._batch]
            try:
                r = await self._http.post(
                    OPENAI_URL, headers={"Authorization": f"Bearer {self._key}"},
                    json={"model": self._model, "input": part})
            except httpx.HTTPError as e:
                raise EmbeddingError(str(e)) from e
            if r.status_code != 200:
                raise EmbeddingError(f"OpenAI {r.status_code}: {r.text[:200]}")
            data = sorted(r.json()["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in data)
        return out


def _is_rate_limit(e):
    return getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e)


class GeminiEmbedder:
    """Google Gemini API (google-genai SDK). Ücretsiz katmanda kota düşüktür: 429 gelince
    bekleyip yeniden dener, bu yüzden büyük kaynaklar yavaş ama kesintisiz vektörlenir."""

    def __init__(self, api_key, model=GEMINI_DEFAULT_MODEL, dimensions=DIMENSIONS, client=None,
                 batch=32, max_retries=6):
        if client is None:
            from google import genai
            client = genai.Client(api_key=api_key)
        self._client, self._model, self._dim = client, model, dimensions
        self._batch, self._max_retries = batch, max_retries
        self.model_id = f"gemini:{model}@{dimensions}"

    async def embed(self, texts, kind="document"):
        """kind='document' belgeler için, kind='query' arama sorguları için (Gemini ikisini ayırır)."""
        from google.genai import types
        config = types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT",
            output_dimensionality=self._dim)
        out = []
        for i in range(0, len(texts), self._batch):
            out.extend(await self._call(texts[i:i + self._batch], config))
        return out

    async def _call(self, part, config):
        delay = 2.0
        for attempt in range(self._max_retries):
            try:
                res = await self._client.aio.models.embed_content(
                    model=self._model, contents=part, config=config)
                return [list(e.values) for e in res.embeddings]
            except Exception as e:
                if _is_rate_limit(e) and attempt < self._max_retries - 1:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                raise EmbeddingError(str(e)) from e


def make_embedder(env=None):
    """EMBEDDING_PROVIDER=gemini|openai. Belirtilmezse GEMINI_API_KEY varsa Gemini, yoksa
    OPENAI_API_KEY varsa OpenAI. İkisi de yoksa None (RAG kapalı)."""
    env = os.environ if env is None else env
    provider = (env.get("EMBEDDING_PROVIDER") or "").strip().lower()
    if not provider:
        provider = "gemini" if env.get("GEMINI_API_KEY") else ("openai" if env.get("OPENAI_API_KEY") else "")
    model = env.get("EMBEDDING_MODEL") or None
    if provider == "gemini" and env.get("GEMINI_API_KEY"):
        return GeminiEmbedder(env["GEMINI_API_KEY"], model or GEMINI_DEFAULT_MODEL)
    if provider == "openai" and env.get("OPENAI_API_KEY"):
        return OpenAIEmbedder(env["OPENAI_API_KEY"], model or OPENAI_DEFAULT_MODEL)
    return None