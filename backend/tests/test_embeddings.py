import httpx
import pytest

from app.rag.embeddings import EmbeddingError, OpenAIEmbedder


def make(handler, batch=2):
    return OpenAIEmbedder("anahtar", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)), batch=batch)


async def test_partiler_halinde_ve_sirayi_koruyarak_vektorler():
    cagrilar = []

    def handler(req):
        import json
        girdi = json.loads(req.content)["input"]
        cagrilar.append(girdi)
        assert req.headers["authorization"] == "Bearer anahtar"
        # sırayı bilerek ters döndür: index'e göre sıralanmalı
        return httpx.Response(200, json={"data": [
            {"index": i, "embedding": [float(len(t))]} for i, t in reversed(list(enumerate(girdi)))]})

    sonuc = await make(handler).embed(["a", "bb", "ccc"])
    assert sonuc == [[1.0], [2.0], [3.0]]
    assert cagrilar == [["a", "bb"], ["ccc"]]


async def test_hata_embeddingError():
    with pytest.raises(EmbeddingError):
        await make(lambda r: httpx.Response(401, json={"error": "x"})).embed(["a"])