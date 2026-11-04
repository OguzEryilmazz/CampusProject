import sys

import requests

durak = sys.argv[1]
hat = sys.argv[2] if len(sys.argv) > 2 else None

HEADERS = {"User-Agent": "okul-bitirme-projesi/0.1"}

adaylar = [
    ("egomac / durak",
     "https://egocptsrvand.ego.gov.tr/mblSrv14/service.asp",
     {"FNC": "Otobusler", "DURAK": durak}),
    ("egomac / http",
     "http://egocptsrvand.ego.gov.tr/mblSrv14/service.asp",
     {"FNC": "Otobusler", "DURAK": durak}),
    ("EgoPy / durak",
     "http://88.255.141.70/mobil/iphonenew/durak.asp",
     {"Fnc": "DurakAra", "Query": durak, "Type": "true"}),
]
if hat:
    adaylar.append((
        "egomac / hat",
        "https://egocptsrvand.ego.gov.tr/mblSrv14/service.asp",
        {"FNC": "Otobus", "HAT": hat, "DURAK": durak},
    ))

for ad, url, params in adaylar:
    print("=" * 70)
    print(ad)
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        print("URL:", r.url)
        print("durum:", r.status_code, "|", r.headers.get("content-type"))
        print(r.text[:1500])
    except Exception as e:
        print("HATA:", e)