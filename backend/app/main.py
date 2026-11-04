import os
import re
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .ego import EgoClient, EgoError

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Akıllı Kampüs API")
ego = EgoClient()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


def _origin(url):
    """https://xyz.supabase.co/rest/v1/ gibi yola sahip adreslerden yalnızca kökü alır."""
    if not url:
        return None
    p = urlparse(url.strip())
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else None


@app.get("/config")
def config():
    # Supabase anon anahtarı istemciye açık olacak şekilde tasarlanmıştır,
    # yetki satır düzeyinde güvenlik (RLS) ile sağlanır. service_role anahtarı ASLA burada olmaz.
    return {
        "supabase_url": _origin(os.environ.get("SUPABASE_URL")),
        "supabase_anon_key": os.environ.get("SUPABASE_ANON_KEY"),
    }


@app.get("/stops/{durak_no}/arrivals")
async def arrivals(durak_no: str):
    if not re.fullmatch(r"\d{1,7}", durak_no):
        raise HTTPException(422, "Durak numarası yalnızca rakamlardan oluşmalı")
    try:
        return await ego.arrivals(durak_no)
    except EgoError:
        raise HTTPException(503, "EGO'dan veri alınamadı, resmi tarifeye bakınız")