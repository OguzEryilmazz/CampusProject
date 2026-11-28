"""RAG değerlendirme ölçümleri. Saf fonksiyonlar: ağ, veritabanı ya da .env gerektirmez."""
import json
import statistics
import unicodedata

TURLER = ("ilgili", "alakasiz")
GRUPLAR = ("tamamen_alakasiz", "alan_ici_yok")   # alakasız soruların alt grupları


def norm(s):
    """Türkçe harfleri ASCII'ye indirip küçültür: 'İ'/'ı' -> 'i', 'ş' -> 's' ..."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("ı", "i").casefold().strip()


# ------------------------------------------------------------------ soru seti
def load_questions(path):
    """Soru dosyasını okur ve doğrular. Hatalı satır varsa neden ve sırasıyla ValueError fırlatır."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError("Soru dosyası boş olmayan bir liste olmalı")
    out = []
    for i, q in enumerate(data, 1):
        ad = f"{i}. soru"
        if not isinstance(q, dict) or not str(q.get("soru", "")).strip():
            raise ValueError(f"{ad}: 'soru' metni yok")
        if q.get("tur") not in TURLER:
            raise ValueError(f"{ad}: 'tur' {TURLER} değerlerinden biri olmalı")
        item = dict(q)
        if q["tur"] == "ilgili":
            b = q.get("beklenen")
            if not isinstance(b, list) or not b or not all(isinstance(x, dict) and x.get("baslik") for x in b):
                raise ValueError(f"{ad}: ilgili soruda 'beklenen' listesi (her biri 'baslik' içeren) gerekli")
        else:
            item["grup"] = q.get("grup", "tamamen_alakasiz")
            if item["grup"] not in GRUPLAR:
                raise ValueError(f"{ad}: 'grup' {GRUPLAR} değerlerinden biri olmalı")
        out.append(item)
    return out


# ------------------------------------------------------------------ eşleştirme
def hit_matches(hit, beklenen):
    """Sonuç, beklenen listesindeki herhangi bir kayda uyuyor mu? baslik: içerme, madde: eşitlik."""
    for b in beklenen:
        if norm(b["baslik"]) not in norm(hit.get("baslik")):
            continue
        if b.get("madde") and norm(b["madde"]) != norm(hit.get("madde")):
            continue
        return True
    return False


def build_record(q, hits):
    """Bir sorunun sonucunu özetler: ilk doğru sonucun sırası ve en yüksek skor."""
    rec = {
        "soru": q["soru"], "tur": q["tur"], "grup": q.get("grup"),
        "en_yuksek": float(hits[0]["score"]) if hits else 0.0,
        "sonuclar": [{"baslik": h.get("baslik"), "madde": h.get("madde"), "score": h["score"]} for h in hits],
        "sira": None,
    }
    if q["tur"] == "ilgili":
        for i, h in enumerate(hits, 1):
            if hit_matches(h, q["beklenen"]):
                rec["sira"] = i
                break
    return rec


# ------------------------------------------------------------------ özetleme
def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, round(p * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def stats(values):
    if not values:
        return None
    v = sorted(values)
    return {"n": len(v), "min": v[0], "medyan": statistics.median(v), "p90": _pct(v, 0.9), "maks": v[-1]}


def threshold_analysis(ilgili_skorlar, alakasiz_skorlar):
    """'Skor >= esik ise cevap ver' kuralı için: ilgili soruların kaçı cevaplanır (tpr),
    alakasız soruların kaçı YANLIŞLIKLA cevaplanır (fpr)."""
    if not ilgili_skorlar or not alakasiz_skorlar:
        return None
    rows = []
    for t in sorted(set(ilgili_skorlar) | set(alakasiz_skorlar)):
        tpr = sum(s >= t for s in ilgili_skorlar) / len(ilgili_skorlar)
        fpr = sum(s >= t for s in alakasiz_skorlar) / len(alakasiz_skorlar)
        rows.append({"esik": t, "tpr": tpr, "fpr": fpr, "j": tpr - fpr})
    onerilen = max(rows, key=lambda r: (r["j"], r["esik"]))   # eşitlikte daha yüksek eşik
    guvenli = min((r for r in rows if r["fpr"] == 0), key=lambda r: r["esik"], default=None)
    return {"onerilen": onerilen, "guvenli": guvenli, "satirlar": rows}


def summarize(records):
    ok = [r for r in records if "hata" not in r]
    ilgili = [r for r in ok if r["tur"] == "ilgili"]
    alak = [r for r in ok if r["tur"] == "alakasiz"]
    s = {"n_ilgili": len(ilgili), "n_alakasiz": len(alak), "n_hata": len(records) - len(ok), "uyarilar": []}
    if ilgili:
        s["top1"] = sum(r["sira"] == 1 for r in ilgili) / len(ilgili)
        s["topk"] = sum(r["sira"] is not None for r in ilgili) / len(ilgili)
        s["mrr"] = sum(1 / r["sira"] for r in ilgili if r["sira"]) / len(ilgili)
        s["ilgili_skor"] = stats([r["en_yuksek"] for r in ilgili])
        s["dogru_top1_skor"] = stats([r["en_yuksek"] for r in ilgili if r["sira"] == 1])
    if alak:
        s["alakasiz_skor"] = stats([r["en_yuksek"] for r in alak])
        s["alakasiz_gruplar"] = {
            g: stats([r["en_yuksek"] for r in alak if r["grup"] == g]) for g in GRUPLAR
            if any(r["grup"] == g for r in alak)}
    s["esik"] = threshold_analysis([r["en_yuksek"] for r in ilgili], [r["en_yuksek"] for r in alak])

    if len(ilgili) < 20:
        s["uyarilar"].append(f"İlgili soru sayısı {len(ilgili)} (en az 20 önerilir): eşik güvenilir değil.")
    if len(alak) < 10:
        s["uyarilar"].append(f"Alakasız soru sayısı {len(alak)} (en az 10 önerilir): eşik güvenilir değil.")
    if s["esik"] and s["esik"]["guvenli"] is None:
        s["uyarilar"].append("Alakasız soruların en yüksek skoru ilgili soruların en düşüğünden yüksek ya da eşit: "
                             "skorla ayırt edilemiyor, ek bir doğrulama katmanı gerekir.")
    if s["n_hata"]:
        s["uyarilar"].append(f"{s['n_hata']} soru hata verdi ve ölçüme katılmadı.")
    return s


# ------------------------------------------------------------------ rapor
def _f(x):
    return "-" if x is None else f"{x:.3f}"


def _stat_line(st):
    return "-" if not st else (f"n={st['n']}, min {_f(st['min'])}, medyan {_f(st['medyan'])}, "
                              f"p90 {_f(st['p90'])}, maks {_f(st['maks'])}")


def markdown_report(meta, records, s):
    L = [f"# RAG değerlendirme raporu", "",
         f"- Tarih: {meta.get('tarih')}",
         f"- Vektörleme: `{meta.get('model_id')}`",
         f"- Rol / fakülte: `{meta.get('rol')}` / `{meta.get('fakulte')}`, k = {meta.get('k')}",
         f"- Soru sayısı: {s['n_ilgili']} ilgili, {s['n_alakasiz']} alakasız", ""]
    if s["uyarilar"]:
        L += ["## Uyarılar", ""] + [f"- {u}" for u in s["uyarilar"]] + [""]
    if s["n_ilgili"]:
        L += ["## İlgili sorular", "",
              f"- İlk sonuç doğru (top-1): **{s['top1']:.0%}**",
              f"- İlk {meta.get('k')} içinde doğru (top-k): **{s['topk']:.0%}**",
              f"- MRR: **{s['mrr']:.3f}**",
              f"- En yüksek skor dağılımı: {_stat_line(s['ilgili_skor'])}",
              f"- Doğru bulunanların skoru: {_stat_line(s['dogru_top1_skor'])}", ""]
    if s["n_alakasiz"]:
        L += ["## Alakasız sorular (en yüksek skor ne kadar yüksek çıkıyor?)", "",
              f"- Tümü: {_stat_line(s['alakasiz_skor'])}"]
        for g, st in s["alakasiz_gruplar"].items():
            L.append(f"- {g}: {_stat_line(st)}")
        L.append("")
    e = s["esik"]
    if e:
        o, g = e["onerilen"], e["guvenli"]
        L += ["## Eşik önerisi", "",
              f"- **En iyi ayıran eşik:** {_f(o['esik'])} (ilgili soruların {o['tpr']:.0%}'i cevaplanır, "
              f"alakasızların {o['fpr']:.0%}'i yanlışlıkla cevaplanır)"]
        L.append(f"- **Güvenli eşik (alakasızların hiçbiri geçmez):** {_f(g['esik'])} "
                 f"(ilgili soruların {g['tpr']:.0%}'i cevaplanır)" if g else
                 "- Güvenli eşik yok: hiçbir eşik alakasız soruları tamamen dışarıda bırakmıyor.")
        L += ["", "Öneri: güvenli eşik ve en iyi ayıran eşik arasında kalan skorlar için "
                  "\"kesin bir kaynak bulamadım, en yakın olabilecek şu\" de; altında \"bulamadım\" de.", ""]
    yanlis = [r for r in records if r.get("tur") == "ilgili" and "hata" not in r and r["sira"] != 1]
    if yanlis:
        L += ["## Doğru kaynağı ilk sırada getirmeyen ilgili sorular", ""]
        for r in yanlis:
            ilk = ", ".join(f"{x['baslik']} {x['madde'] or ''} ({x['score']:.2f})".strip() for x in r["sonuclar"][:3])
            L.append(f"- «{r['soru']}» → doğru sıra: {r['sira'] or 'yok'}; ilk sonuçlar: {ilk}")
        L.append("")
    riskli = sorted((r for r in records if r.get("tur") == "alakasiz" and "hata" not in r),
                    key=lambda r: -r["en_yuksek"])[:5]
    if riskli:
        L += ["## Alakasız olduğu halde en yüksek skor alan sorular", ""]
        L += [f"- {r['en_yuksek']:.3f} «{r['soru']}» ({r['grup']})" for r in riskli] + [""]
    return "\n".join(L)
