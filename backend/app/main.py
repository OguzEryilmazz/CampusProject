import asyncio
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from .auth import get_current_user, password_login
from .config import (firebase_service_account_file, service_role_key, supabase_anon_key,
                     supabase_url)
from .db import Db
from .ego import EgoClient, EgoError
from .push import FcmSender, service_account_provider
from .rag.embeddings import make_embedder
from .rag.search import search as rag_search
from .schemas import (ArrivalsOut, HealthOut, NotificationOut, ProfileOut, SearchOut, StopOut,
                      TokenOut)
from .scheduler import TZ, safe_run

VERSION = "0.4.0"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

STATIC = Path(__file__).parent / "static"
ego = EgoClient()
state = {"db": None, "push": None, "embedder": None, "scheduler": False}


@asynccontextmanager
async def lifespan(app):
    sched = None
    url, key = supabase_url(), service_role_key()
    if url and key:
        state["db"] = db = Db(url, key)
        sa = firebase_service_account_file()
        if sa:
            try:
                project_id, provider = service_account_provider(sa)
                state["push"] = FcmSender(project_id, provider)
                log.info("Push açık (Firebase projesi: %s)", project_id)
            except Exception:
                log.exception("Firebase hizmet hesabı okunamadı, push kapalı")
        else:
            log.warning("FIREBASE_SERVICE_ACCOUNT_FILE yok: push kapalı, bildirimler yalnızca kaydedilir")
        state["embedder"] = make_embedder()
        if state["embedder"]:
            log.info("RAG araması açık (%s)", state["embedder"].model_id)
        else:
            log.warning("GEMINI_API_KEY / OPENAI_API_KEY yok: RAG araması kapalı")
        sched = AsyncIOScheduler(timezone=TZ)
        sched.add_job(safe_run, "interval", seconds=60, args=[db, ego, state["push"]],
                      max_instances=1, coalesce=True)
        sched.start()
        state["scheduler"] = True
        log.info("Bildirim zamanlayıcısı başladı (60 sn aralık)")
    else:
        log.warning("SUPABASE_SERVICE_ROLE_KEY yok: bildirim zamanlayıcısı kapalı")
    yield
    if sched:
        sched.shutdown(wait=False)


DESCRIPTION = """
**Akıllı Kampüs Asistanı** backend'i. Ankara Üniversitesi öğrencileri ve personeli için canlı otobüs
bildirimleri ve okul dokümanlarında kaynaklı arama sunar.

### Bu sayfayı denemek için
1. Sağ üstteki **Authorize** düğmesine tıkla.
2. Supabase'teki **e-posta ve şifreni** gir (`username` alanına e-posta). Diğer alanlar boş kalabilir.
3. Bir uç noktayı aç, **Try it out** ve **Execute** de. Yanıtı ve örnek isteği hemen görürsün.

### Notlar
* Otobüs verisi EGO'nun **resmi olmayan** servisinden gelir. Aynı durak için 30 sn önbellek kullanılır.
* `Kullanıcı` altındaki uç noktalar giriş yapan kişinin kendi verisini döndürür.
* Bildirimleri bu API değil zamanlayıcı üretir; buradan yalnızca okunur.
"""

TAGS = [
    {"name": "Sistem", "description": "Sunucu durumu ve istemci ayarları. Giriş gerekmez."},
    {"name": "Kimlik", "description": "Giriş. Mobil uygulama Supabase ile doğrudan giriş yapar; bu uç nokta bu sayfadaki deneme içindir."},
    {"name": "Kullanıcı", "description": "Giriş yapan kullanıcının profili, favori durakları ve bildirimleri."},
    {"name": "Duraklar", "description": "Bir durağa yaklaşan canlı araçlar (EGO)."},
    {"name": "Cihazlar", "description": "Push bildirimi için telefonun FCM token'ının kaydı."},
    {"name": "Doküman arama", "description": "Okul dokümanlarında (yönetmelik, duyuru) kaynaklı arama. Rol ve fakülte profilden alınır."},
]

app = FastAPI(title="Akıllı Kampüs API", version=VERSION, description=DESCRIPTION,
              openapi_tags=TAGS, lifespan=lifespan)


def _db():
    if not state["db"]:
        raise HTTPException(503, "Sunucu ayarı eksik (service_role anahtarı)")
    return state["db"]


# ---------------------------------------------------------------- Sistem
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health", tags=["Sistem"], response_model=HealthOut, summary="Sunucu durumu")
def health():
    """Sunucu ayakta mı ve hangi bileşenler açık? Anahtarlar ya da gizli değerler gösterilmez."""
    return {"durum": "ok", "surum": VERSION, "ozellikler": {
        "veritabani": state["db"] is not None,
        "zamanlayici": state["scheduler"],
        "push": state["push"] is not None,
        "rag": state["embedder"] is not None,
    }}


@app.get("/config", tags=["Sistem"], summary="İstemci ayarları")
def config():
    """Mobil uygulamanın Supabase'e bağlanması için adres ve **anon** anahtar.

    Anon anahtar istemciye açık olacak şekilde tasarlanmıştır, yetki satır düzeyinde güvenlikle
    sağlanır. `service_role` anahtarı ve Firebase hizmet hesabı asla burada olmaz.
    """
    return {"supabase_url": supabase_url(), "supabase_anon_key": supabase_anon_key()}


# ---------------------------------------------------------------- Kimlik
@app.post("/auth/token", tags=["Kimlik"], response_model=TokenOut, summary="E-posta ve şifreyle giriş")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Supabase hesabıyla giriş yapar ve erişim token'ı döndürür (`username` = e-posta)."""
    return {"access_token": await password_login(form.username, form.password), "token_type": "bearer"}


# ---------------------------------------------------------------- Kullanıcı
@app.get("/me", tags=["Kullanıcı"], response_model=ProfileOut, summary="Profilim")
async def me(user: dict = Depends(get_current_user)):
    """Adım, rolüm, fakültem, kampüsüm ve bildirim ayarım."""
    prof = await _db().profile_of(user["id"])
    if not prof:
        raise HTTPException(404, "Profil bulunamadı")
    return prof


@app.get("/me/stops", tags=["Kullanıcı"], response_model=list[StopOut],
         summary="Favori duraklarım ve canlı araçlar (filtrelenmiş)")
async def my_stops(user: dict = Depends(get_current_user)):
    """Favori duraklarım ve her durakta **yalnızca kampüsüme hizmet veren hatların** canlı araçları.

    Kampüsüm için hat listesi tanımlı değilse tüm araçlar gösterilir (`filtre_aktif: false`).
    """
    db = _db()
    stops, prof = await asyncio.gather(db.favorite_stops_of(user["id"]), db.profile_of(user["id"]))
    kampus = (prof or {}).get("kampus")
    hatlar = (await db.campus_lines([kampus])).get(kampus, set()) if kampus else set()

    async def one(s):
        try:
            arr = await ego.arrivals(s["durak_no"])
        except EgoError:
            return {**s, "canli": [], "filtre_aktif": bool(hatlar), "veri_alinamadi": True, "stale": False}
        canli = [v for v in arr["canli"] if v["hat_no"] in hatlar] if hatlar else arr["canli"]
        return {**s, "canli": canli, "filtre_aktif": bool(hatlar), "veri_alinamadi": False,
                "stale": arr["stale"]}

    return await asyncio.gather(*(one(s) for s in stops))


@app.get("/me/notifications", tags=["Kullanıcı"], response_model=list[NotificationOut],
         summary="Son bildirimlerim")
async def my_notifications(limit: int = Query(20, ge=1, le=100, description="En fazla kaç bildirim"),
                           user: dict = Depends(get_current_user)):
    """Bana üretilen bildirimler, en yeniden eskiye. `sent_at` boşsa bildirim yalnızca kaydedilmiştir, push gitmemiştir."""
    return await _db().notifications_of(user["id"], limit)


# ---------------------------------------------------------------- Duraklar
@app.get("/stops/{durak_no}/arrivals", tags=["Duraklar"], response_model=ArrivalsOut,
         summary="Bir durağa yaklaşan araçlar (ham)")
async def arrivals(durak_no: str, user: dict = Depends(get_current_user)):
    """Durağa yaklaşan **tüm** canlı araçlar ve tarife satırları, filtresiz.

    Kampüs hatlarına göre filtrelenmiş görünüm için `/me/stops` kullanılır.
    """
    if not re.fullmatch(r"\d{1,7}", durak_no):
        raise HTTPException(422, "Durak numarası yalnızca rakamlardan oluşmalı")
    try:
        return await ego.arrivals(durak_no)
    except EgoError:
        raise HTTPException(503, "EGO'dan veri alınamadı, resmi tarifeye bakınız")


# ---------------------------------------------------------------- Cihazlar
class DeviceIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096, description="FCM cihaz token'ı")
    platform: Literal["android", "ios"] = "android"


@app.post("/devices", tags=["Cihazlar"], status_code=204, summary="Cihazımı kaydet")
async def register_device(body: DeviceIn, user: dict = Depends(get_current_user)):
    """Mobil uygulama, FCM cihaz token'ını giriş yaptıktan sonra buraya kaydeder."""
    await _db().upsert_device(user["id"], body.token, body.platform)


@app.delete("/devices/{token}", tags=["Cihazlar"], status_code=204, summary="Cihazımı kaldır")
async def unregister_device(token: str, user: dict = Depends(get_current_user)):
    """Çıkış yaparken cihazın bildirim almasını durdurur (yalnızca kendi cihazı)."""
    await _db().delete_device(token, user_id=user["id"])


# ---------------------------------------------------------------- Doküman arama
@app.get("/rag/search", tags=["Doküman arama"], response_model=SearchOut, summary="Dokümanlarda ara")
async def rag_search_endpoint(q: str = Query(min_length=2, max_length=500, description="Soru ya da arama metni"),
                              k: int = Query(5, ge=1, le=10, description="Kaç parça döndürülsün"),
                              user: dict = Depends(get_current_user)):
    """Okul dokümanlarında arama. Rol ve fakülte **profilimden** alınır, istemciden gönderilemez."""
    db = _db()
    if not state["embedder"]:
        raise HTTPException(503, "RAG ayarı eksik (GEMINI_API_KEY ya da OPENAI_API_KEY)")
    rol, fakulte = await db.user_scope(user["id"])
    try:
        return {"sonuclar": await rag_search(db, state["embedder"], q, rol, fakulte, k)}
    except Exception:
        log.exception("RAG araması başarısız")
        raise HTTPException(503, "Arama şu an yapılamıyor")