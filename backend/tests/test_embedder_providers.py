import pytest

from app.rag import embeddings as emb
from app.rag.embeddings import (EmbeddingError, GeminiEmbedder, OpenAIEmbedder, make_embedder)


class _Vec:
    def __init__(self, v):
        self.values = v


class _Resp:
    def __init__(self, n, dim):
        self.embeddings = [_Vec([float(i)] * dim) for i in range(n)]


class FakeModels:
    def __init__(self, hatalar=()):
        self.cagrilar, self.hatalar = [], list(hatalar)

    async def embed_content(self, *, model, contents, config=None):
        self.cagrilar.append({"model": model, "contents": list(contents), "config": config})
        if self.hatalar:
            raise self.hatalar.pop(0)
        return _Resp(len(contents), config.output_dimensionality)


class _Aio:
    def __init__(self, models):
        self.models = models


class FakeClient:
    def __init__(self, models):
        self.aio = _Aio(models)


class RateLimit(Exception):
    code = 429


@pytest.fixture(autouse=True)
def hizli_bekleme(monkeypatch):
    async def yok(_):
        return None
    monkeypatch.setattr(emb.asyncio, "sleep", yok)


def make(models, **kw):
    return GeminiEmbedder("k", client=FakeClient(models), **kw)


async def test_gemini_partiler_boyut_ve_gorev_tipi():
    m = FakeModels()
    g = make(m, batch=2, dimensions=1536)
    sonuc = await g.embed(["a", "b", "c"], kind="document")
    assert len(sonuc) == 3 and len(sonuc[0]) == 1536
    assert [c["contents"] for c in m.cagrilar] == [["a", "b"], ["c"]]
    assert m.cagrilar[0]["model"] == "gemini-embedding-001"
    assert m.cagrilar[0]["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert m.cagrilar[0]["config"].output_dimensionality == 1536
    await g.embed(["soru"], kind="query")
    assert m.cagrilar[-1]["config"].task_type == "RETRIEVAL_QUERY"
    assert g.model_id == "gemini:gemini-embedding-001@1536"


async def test_gemini_kota_hatasinda_bekleyip_yeniden_dener():
    m = FakeModels(hatalar=[RateLimit("429 RESOURCE_EXHAUSTED"), RateLimit("429")])
    sonuc = await make(m).embed(["a"])
    assert len(sonuc) == 1 and len(m.cagrilar) == 3     # 2 başarısız + 1 başarılı


async def test_gemini_kota_surekli_asilirsa_embeddingerror():
    m = FakeModels(hatalar=[RateLimit("429")] * 10)
    with pytest.raises(EmbeddingError):
        await make(m, max_retries=3).embed(["a"])
    assert len(m.cagrilar) == 3


async def test_gemini_diger_hatalar_beklemeden_embeddingerror():
    m = FakeModels(hatalar=[RuntimeError("anahtar geçersiz")])
    with pytest.raises(EmbeddingError):
        await make(m).embed(["a"])
    assert len(m.cagrilar) == 1


def test_make_embedder_secimi():
    assert make_embedder({}) is None
    assert isinstance(make_embedder({"GEMINI_API_KEY": "g"}), GeminiEmbedder)
    assert isinstance(make_embedder({"OPENAI_API_KEY": "o"}), OpenAIEmbedder)
    # ikisi de varsa Gemini öncelikli, EMBEDDING_PROVIDER ile değiştirilebilir
    ikisi = {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o"}
    assert isinstance(make_embedder(ikisi), GeminiEmbedder)
    assert isinstance(make_embedder({**ikisi, "EMBEDDING_PROVIDER": "openai"}), OpenAIEmbedder)
    # sağlayıcı seçili ama anahtarı yoksa RAG kapalı kalır, sessizce başka sağlayıcıya geçmez
    assert make_embedder({"EMBEDDING_PROVIDER": "gemini", "OPENAI_API_KEY": "o"}) is None
    assert make_embedder({"GEMINI_API_KEY": "g", "EMBEDDING_MODEL": "baska-model"}).model_id.startswith("gemini:baska-model")
