import httpx
import pytest

from app.push import FcmSender, PushError


def make(handler):
    async def provider():
        return "erisim-tokeni"
    return FcmSender("proje-x", provider, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_basarili_gonderim_dogru_istek():
    gorulen = {}

    def handler(req):
        import json
        gorulen["url"] = str(req.url)
        gorulen["auth"] = req.headers["authorization"]
        gorulen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"name": "projects/proje-x/messages/1"})

    sonuc = await make(handler).send("tok" * 10, "Başlık", "Gövde", {"durak_no": "12579", "notification_id": 7})
    assert sonuc == "ok"
    assert gorulen["url"] == "https://fcm.googleapis.com/v1/projects/proje-x/messages:send"
    assert gorulen["auth"] == "Bearer erisim-tokeni"
    m = gorulen["body"]["message"]
    assert m["token"] == "tok" * 10
    assert m["notification"] == {"title": "Başlık", "body": "Gövde"}
    assert m["data"] == {"durak_no": "12579", "notification_id": "7"}   # data değerleri metin olmalı
    assert m["android"]["priority"] == "HIGH"


async def test_kayitsiz_cihaz_invalid_doner():
    r = httpx.Response(404, json={"error": {"status": "NOT_FOUND",
                                            "details": [{"errorCode": "UNREGISTERED"}]}})
    assert await make(lambda req: r).send("t" * 20, "a", "b") == "invalid"


async def test_diger_hatalar_pushError():
    with pytest.raises(PushError):
        await make(lambda req: httpx.Response(500, json={"error": {"message": "iç hata"}})).send("t" * 20, "a", "b")


async def test_kimlik_dogrulama_hatasi_pushError():
    async def bozuk():
        raise RuntimeError("anahtar okunamadı")
    s = FcmSender("p", bozuk, http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))))
    with pytest.raises(PushError):
        await s.send("t" * 20, "a", "b")