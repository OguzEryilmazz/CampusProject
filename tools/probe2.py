import sys
import time

import requests

durak = sys.argv[1]
URL = "https://egocptsrvand.ego.gov.tr/mblSrv14/service.asp"
HEADERS = {"User-Agent": "okul-bitirme-projesi/0.1"}

for i in range(6):  # 6 deneme, 30 sn arayla
    r = requests.get(URL, params={"FNC": "Otobusler", "DURAK": durak},
                     headers=HEADERS, timeout=15)
    satirlar = r.json().get("table", [])
    canli = [s for s in satirlar if s.get("arac_no") not in ("-", "", None)]
    print(f"[{time.strftime('%H:%M:%S')}] toplam {len(satirlar)} satır, canlı araç: {len(canli)}")
    for s in canli:
        print("   ", s["arac_no"], "|", s["hat_no"], "|", s["sure"], "|", s["detay"])
    if i < 5:
        time.sleep(30)