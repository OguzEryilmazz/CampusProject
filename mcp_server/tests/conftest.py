import os

os.environ.setdefault("BACKEND_URL", "http://backend.test")

import httpx
import pytest

from kampus_mcp import auth_middleware, backend_client

IYI = "Bearer iyi-token-1234567890"


@pytest.fixture(autouse=True)
def temiz(monkeypatch):
    backend_client._dogrulanan.clear()
    auth_middleware.istekler.temizle()
    auth_middleware.hatalar.temizle()
    monkeypatch.setattr(backend_client, "_auth_basligi", lambda: IYI)
    yield
    backend_client._transport = None


@pytest.fixture
def sahte_backend():
    """sahte_backend(handler) -> backend_client'a MockTransport takar. Çağrıları .istekler listesinde tutar."""
    def kur(handler):
        istekler = []

        def sarmal(request: httpx.Request):
            istekler.append(request)
            return handler(request)

        backend_client._transport = httpx.MockTransport(sarmal)
        return istekler
    return kur
