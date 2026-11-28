"""Ortam değişkenlerinden yapılandırma. Zorunlu ayar eksikse sunucu başlamaz.
Bu serviste gizli anahtar yoktur: yalnızca backend adresi gerekir."""
import os
from zoneinfo import ZoneInfo


def _zorunlu(ad: str) -> str:
    deger = os.environ.get(ad, "").strip()
    if not deger:
        raise RuntimeError(f"Zorunlu ortam değişkeni eksik: {ad}")
    return deger


BACKEND_URL = _zorunlu("BACKEND_URL").rstrip("/")  # örn. http://127.0.0.1:8000
BACKEND_TIMEOUT_SN = float(os.environ.get("BACKEND_TIMEOUT_SN", "10"))
TOKEN_ONBELLEK_SN = int(os.environ.get("TOKEN_ONBELLEK_SN", "60"))
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8080"))

# Yanıt boyutu sınırları (rehber 6.3)
MAX_ARAC = 10          # bir durak için döndürülen en fazla araç
MAX_BILDIRIM = 20
MAX_ARAMA_SONUCU = 8
ICERIK_MAX_KARAKTER = 700

TZ = ZoneInfo("Europe/Istanbul")  # backend scheduler.py ile aynı; gun alanı isoweekday (1=Pzt … 7=Paz)

# Oran sınırı (tek süreçte bellekte tutulur; sunucu tek süreç çalışmalı)
ISTEK_LIMITI_DK = int(os.environ.get("ISTEK_LIMITI_DK", "60"))   # token başına dakikada istek
HATA_LIMITI_DK = int(os.environ.get("HATA_LIMITI_DK", "10"))     # IP başına dakikada başarısız kimlik denemesi
# Yalnızca güvenilir bir ters vekilin (barındırıcının yük dengeleyicisi) arkasındaysan true yap.
# Doğrudan internete açıkken true olursa istemci X-Forwarded-For'u taklit edip sınırı aşabilir.
GUVEN_VEKIL = os.environ.get("GUVEN_VEKIL", "false").lower() in ("1", "true", "evet")
