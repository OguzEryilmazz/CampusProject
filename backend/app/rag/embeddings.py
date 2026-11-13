import httpx

OPENAI_URL = "https://api.openai.com/v1/embeddings"
DEFAULT_MODEL = "text-embedding-3-small"   # 1536 boyut, şema da buna göre (vector(1536))


class EmbeddingError(Exception):
    pass


class OpenAIEmbedder:
    def __init__(self, api_key, model=DEFAULT_MODEL, http=None, batch=64):
        self._key, self._model, self._batch = api_key, model, batch
        self._http = http or httpx.AsyncClient(timeout=60)

    async def embed(self, texts):
        """Metin listesi -> aynı sırada vektör listesi."""
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