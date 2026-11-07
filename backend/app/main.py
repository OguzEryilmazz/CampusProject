import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse

from .auth import get_current_user
from .config import service_role_key, supabase_anon_key, supabase_url
from .db import Db
from .ego import EgoClient, EgoError
from .scheduler import TZ, safe_run

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

STATIC = Path(__file__).parent / "static"
ego = EgoClient()


@asynccontextmanager
async def lifespan(app):
    sched = None
    url, key = supabase_url(), service_role_key()
    if url and key:
        sched = AsyncIOScheduler(timezone=TZ)
        sched.add_job(safe_run, "interval", seconds=60, args=[Db(url, key), ego],
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
    # service_role anahtarı ASLA burada olmaz.
    return {"supabase_url": supabase_url(), "supabase_anon_key": supabase_anon_key()}


@app.get("/stops/{durak_no}/arrivals")
async def arrivals(durak_no: str, user: dict = Depends(get_current_user)):
    if not re.fullmatch(r"\d{1,7}", durak_no):
        raise HTTPException(422, "Durak numarası yalnızca rakamlardan oluşmalı")
    try:
        return await ego.arrivals(durak_no)
    except EgoError:
        raise HTTPException(503, "EGO'dan veri alınamadı, resmi tarifeye bakınız")