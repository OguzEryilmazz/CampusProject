"""Bologna araçlarının ortak ayarları ve küçük yardımcıları."""
import html
import json
import re
from pathlib import Path

BASE = "https://bologna.ankara.edu.tr"

BACKEND = Path(__file__).resolve().parents[2]   # .../backend
VERI = BACKEND / "data" / "bologna"             # üretilen her şey burada (ham/, yapisal/, metin/)

# Tarayıcıda (Network sekmesi) görülen "ders listesi" isteğinin yolu; gövde: Id, Yil, YilNo.
# Boş bırakılırsa cek.py --liste-yolu ister (ya da BOLOGNA_LISTE_YOLU ortam değişkeni).
DERS_LISTESI_YOLU = ""

# Ders sayfası adresi (program adresi + ders adı) birkaç örnekle tarayıcıda doğrulanınca True yapın.
DERS_URL_DOGRULANDI = False

_TR = str.maketrans("ığüşöçİĞÜŞÖÇ", "igusocIGUSOC")


def slug(s):
    """Dosya adı için: 'Yazılım Mühendisliği' -> 'yazilim-muhendisligi'."""
    s = (s or "").translate(_TR).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"


def url_slug(s):
    """Bologna adres parçası: Türkçe harfler sadeleşir, boşluk ve noktalama silinir.
    'Sayısal Tasarım' -> 'sayisaltasarim' (tek örnekle doğrulandı)."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").translate(_TR).lower())


def temiz(s):
    """HTML etiketlerini ve fazla boşlukları temizler."""
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def js(s):
    """İçinde JSON metni olan alanı listeye çevirir."""
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def tr_baslik(s):
    """'DOÇ. DR. ÜMİT ERTEM' -> 'Doç. Dr. Ümit Ertem' (Türkçe i/ı kurallarıyla)."""
    kucuk = s.replace("İ", "i").replace("I", "ı").lower()
    parcalar = []
    for w in kucuk.split():
        bas = w[0].replace("i", "İ").replace("ı", "I").upper()
        parcalar.append(bas + w[1:])
    return " ".join(parcalar)


def sayi(x):
    if x is None:
        return "-"
    return str(int(x)) if float(x) == int(x) else str(x)


def program_url(duzey, fakulte, ad):
    """Program sayfası adresi. Yalnızca lisans için doğrulandı; diğer düzeylerde None döner."""
    if duzey != "Lisans" or not fakulte:
        return None
    return f"{BASE}/programlar/lisans/{url_slug(fakulte)}/{url_slug(ad)}"
