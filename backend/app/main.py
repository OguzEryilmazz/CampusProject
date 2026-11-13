import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import get_current_user
from .config import (firebase_service_account_file, service_role_key, supabase_anon_key,
                     supabase_url)
from .db import Db
from .ego import EgoClient, EgoError
from .push import FcmSender, service_account_provider
from .rag.embeddings import DEFAULT_MODEL, OpenAIEmbedder
from .rag.search import search as rag_search
from .scheduler import TZ, safe_run

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

STATIC = Path(__file__).parent / "static"
ego = EgoClient()
state = {"db": None, "push": None, "embedder": None}


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
        if os.environ.get("OPENAI_API_KEY"):
            state["embedder"] = OpenAIEmbedder(os.environ["OPENAI_API_KEY"],
                                               os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL))
            log.info("RAG araması açık")
        else:
            log.warning("OPENAI_API_KEY yok: RAG araması kapalı")
        sched = AsyncIOScheduler(timezone=TZ)
        sched.add_job(safe_run, "interval", seconds=60, args=[db, ego, state["push"]],
                      max_instances=1, coalesce=True)
        sched.start()
        log.info("Bildirim zamanlayıcısı başladı (60 sn aralık)")
    else:
        log.warning("SUPABASE_SERVICE_ROLE_KEY yok: bildirim zamanlayıcısı kapalı")
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="Akıllı Kampüs API", lifespan=lifespan)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/config")
def config():
    # Anon anahtarı istemciye açık olacak şekilde tasarlanmıştır (yetki RLS ile sağlanır).
    # service_role anahtarı ve Firebase hizmet hesabı ASLA burada olmaz.
    return {"supabase_url": supabase_url(), "supabase_anon_key": supabase_anon_key()}


@app.get("/stops/{durak_no}/arrivals")
async def arrivals(durak_no: str, user: dict = Depends(get_current_user)):
    if not re.fullmatch(r"\d{1,7}", durak_no):
        raise HTTPException(422, "Durak numarası yalnızca rakamlardan oluşmalı")
    try:
        return await ego.arrivals(durak_no)
    except EgoError:
        raise HTTPException(503, "EGO'dan veri alınamadı, resmi tarifeye bakınız")


class DeviceIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    platform: Literal["android", "ios"] = "android"


def _db():
    if not state["db"]:
        raise HTTPException(503, "Sunucu ayarı eksik (service_role anahtarı)")
    return state["db"]


@app.post("/devices", status_code=204)
async def register_device(body: DeviceIn, user: dict = Depends(get_current_user)):
    """Mobil uygulama, FCM cihaz token'ını giriş yaptıktan sonra buraya kaydeder."""
    await _db().upsert_device(user["id"], body.token, body.platform)


@app.delete("/devices/{token}", status_code=204)
async def unregister_device(token: str, user: dict = Depends(get_current_user)):
    """Çıkış yaparken cihazın bildirim almasını durdurur (yalnızca kendi cihazı)."""
    await _db().delete_device(token, user_id=user["id"])


@app.get("/rag/search")
async def rag_search_endpoint(q: str = Query(min_length=2, max_length=500),
                              k: int = Query(5, ge=1, le=10),
                              user: dict = Depends(get_current_user)):
    """Okul dokümanlarında arama. Rol ve fakülte kullanıcının profilinden alınır, istemciden alınmaz."""
    db = _db()
    if not state["embedder"]:
        raise HTTPException(503, "RAG ayarı eksik (OPENAI_API_KEY)")
    rol, fakulte = await db.user_scope(user["id"])
    try:
        return {"sonuclar": await rag_search(db, state["embedder"], q, rol, fakulte, k)}
    except Exception:
        log.exception("RAG araması başarısız")
        raise HTTPException(503, "Arama şu an yapılamıyor")