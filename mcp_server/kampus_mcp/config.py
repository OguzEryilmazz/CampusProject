"""Ortam değişkenlerinden yapılandırma. Zorunlu ayar eksikse sunucu başlamaz.
Bu serviste gizli anahtar yoktur: yalnızca backend adresi gerekir."""
import os


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
