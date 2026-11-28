"""Bologna API yoklama betigi: yapiyi gormek icin, veri cekmek icin degil.

Calistir:  python probe_bologna.py
Cikti:     probe_out/ klasorune ham yanitlar + ekrana ozet.
Istekler arasinda 1 sn bekler, toplam ~10 istek atar.
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://bologna.ankara.edu.tr"
OUT = "probe_out"
os.makedirs(OUT, exist_ok=True)
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "AkilliKampusAsistani-bitirme/0.1 (ogrenci projesi)",
}


def call(path, payload=None, method="POST"):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if method == "POST" and data is None:
        data = b"{}"
    req = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return None, repr(e)


def describe(obj, depth=0, maxdepth=3):
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:40]:
            t = type(v).__name__
            extra = f"[{len(v)}]" if isinstance(v, (list, dict, str)) else f"= {v!r}"
            print(f"{pad}- {k}: {t} {extra}"[:200])
            if depth < maxdepth and isinstance(v, (dict, list)) and v:
                describe(v, depth + 1, maxdepth)
    elif isinstance(obj, list) and obj:
        print(f"{pad}(liste, {len(obj)} oge; ilk ogenin yapisi:)")
        describe(obj[0], depth + 1, maxdepth)


def save(name, text):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(text)


# 1) index.json
print("== index.json indiriliyor ==")
st, body = call("/api/YzAsistan/index.json", method="GET")
print("durum:", st, "boyut:", len(body))
idx = json.loads(body)
save("index_bolumler_ornek.json", json.dumps(idx["bolumler"][:3], ensure_ascii=False, indent=1))

dok = idx["dokumanlar"]
print("\n== dokumanlar: yapi ==")
describe(dok, maxdepth=2)
save("dokumanlar_ornek.json", json.dumps(dok[:5], ensure_ascii=False, indent=1))
print("\nilk 2 dokuman (kisaltilmis):")
print(json.dumps(dok[:2], ensure_ascii=False, indent=1)[:2500])

# 2) Yazilim Muhendisligi program kimligi
swe = next(b for b in idx["bolumler"] if b["ad"] == "Yazılım Mühendisliği")
pid = swe["id"].removeprefix("bolum-")
print("\nProgram Id:", pid)

# 3) Diger uc noktalar
tests = [
    ("ProgramBilgi_getPublicByProgram", "/api/ProgramBilgi/getPublicByProgram", {"Id": pid}),
    ("AkademikKadro_getByProgram", "/api/PublicAkademikKadro/getByProgram", {"Id": pid}),
    ("MufredatDers_getYillar_Id", "/api/PublicMufredatDers/getYillar", {"Id": pid}),
    ("MufredatDers_getYillar_ProgramId", "/api/PublicMufredatDers/getYillar", {"ProgramId": pid}),
]
for name, path, payload in tests:
    time.sleep(1)
    st, body = call(path, payload)
    print(f"\n== {name}  durum={st}  boyut={len(body)} ==")
    save(name + ".json", body)
    try:
        describe(json.loads(body), maxdepth=2)
    except Exception:  # noqa: BLE001
        print(body[:600])

print("\nBitti. probe_out/ klasorundeki dosyalara bakabilirsiniz.")