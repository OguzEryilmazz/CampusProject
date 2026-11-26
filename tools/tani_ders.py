"""Ders detayi 400 hatasinin nedenini bulur. scrape_bologna.py ile ayni klasorde calistirin.

  python tani_ders.py

raw/liste/ altindaki onbellege alinmis ders listesini okur, birkac govde bicimini dener,
her birinin durum kodunu ve (hata ise) sunucunun mesajini yazar. ~8 istek atar.
"""
import glob
import json
import time
import urllib.error
import urllib.request

BASE = "https://bologna.ankara.edu.tr"
PATH = "/api/DersBilgi/getPublicById"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "AkilliKampusAsistani-bitirme/0.1 (ogrenci projesi)",
}
BILINEN_DETAY_ID = "e6ac8bcb-e1b4-42e9-ae6f-6dcd644b02a5"  # tarayicida gordugumuz Matematik I
YIL_ID = "32000000-0000-0000-0000-000000000077"            # 2026 - 2027


def deneme(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + PATH, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return None, repr(e)


def goster(etiket, payload):
    st, body = deneme(payload)
    ozet = body[:300].replace("\n", " ")
    if st == 200:
        try:
            d = json.loads(body)["data"]
            ozet = f"OK -> {d.get('dersKodu')} {d.get('dersAdi')}"
        except Exception:  # noqa: BLE001
            pass
    print(f"[{st}] {etiket}: {json.dumps(payload)[:90]}\n      {ozet}\n")
    time.sleep(1)
    return st


dosyalar = glob.glob("raw/liste/*.json")
if not dosyalar:
    raise SystemExit("raw/liste/ bos. Once scrape_bologna.py ile ders listesi cekilmis olmali.")
liste = json.load(open(dosyalar[0], encoding="utf-8"))["data"]
print(f"{dosyalar[0]}: {len(liste)} ders")
print("Liste ogesinin alanlari:", sorted(liste[0].keys()), "\n")

mat = next((d for d in liste if d.get("dersKodu") == "MAT0143"), None)
if mat:
    print("MAT0143 listedeki id:", mat["id"])
    print("Tarayicidaki detay id:", BILINEN_DETAY_ID)
    print("Ikisi ayni mi?", mat["id"] == BILINEN_DETAY_ID, "\n")

print("== 1) Bilinen (tarayicida calisan) detay kimligi ==")
goster("bilinen id, {Id}", {"Id": BILINEN_DETAY_ID})

d0 = liste[0]
print(f"== 2) Listedeki ilk ders: {d0.get('dersKodu')} ==")
i = d0["id"]
goster("{Id}", {"Id": i})
goster("{Id, id}", {"Id": i, "id": i})
goster("{id}", {"id": i})
goster("{Id, AkademikYilId}", {"Id": i, "AkademikYilId": YIL_ID})
goster("{DersId}", {"DersId": i})
print("Bitti. Tum ciktiyi bana yapistirin.")