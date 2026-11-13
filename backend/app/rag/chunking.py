"""Doküman parçalama. Yönetmelikler MADDE sınırlarında, diğer metinler paragraflarda bölünür."""
import re

MAX_CHARS = 1200   # bir parçanın yaklaşık üst sınırı
OVERLAP = 150      # uzun maddeler bölünürken parçalar arası örtüşme

MADDE_RE = re.compile(r"(?m)^[ \t]*((?:(?:GEÇİCİ|Geçici)\s+)?(?:MADDE|Madde)\s+\d+)\s*[-–—]")


def normalize(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_units(text):
    """Metni cümle/paragraf birimlerine ayırır; hiçbir birim MAX_CHARS'ı aşmaz."""
    units = []
    for para in re.split(r"\n+", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= MAX_CHARS:
            units.append(para)
            continue
        for sent in re.split(r"(?<=[.!?;:])\s+", para):
            while len(sent) > MAX_CHARS:                    # noktalamasız dev cümle
                cut = sent.rfind(" ", 0, MAX_CHARS)
                cut = cut if cut > 0 else MAX_CHARS
                units.append(sent[:cut])
                sent = sent[cut:].strip()
            if sent:
                units.append(sent)
    return units


def _pack(text):
    """Birimleri MAX_CHARS'a kadar birleştirir; ardışık parçalar OVERLAP kadar örtüşür."""
    pieces, cur = [], ""
    for u in _split_units(text):
        if cur and len(cur) + 1 + len(u) > MAX_CHARS:
            pieces.append(cur)
            tail = cur[-OVERLAP:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else tail   # kelime ortasından başlama
            cur = u if len(tail) + 1 + len(u) > MAX_CHARS else f"{tail} {u}".strip()  # örtüşme sınırı aşmasın
        else:
            cur = f"{cur}\n{u}".strip() if cur else u
    if cur:
        pieces.append(cur)
    return pieces


def chunk_text(text, baslik):
    """[{'madde': 'Madde 12' | None, 'icerik': '...'}] döndürür. Her parçanın başına başlık eklenir."""
    text = normalize(text)
    if not text:
        return []
    hits = list(MADDE_RE.finditer(text))
    segments = []   # (madde, metin)
    if len(hits) >= 2:
        if text[:hits[0].start()].strip():
            segments.append((None, text[:hits[0].start()].strip()))
        for i, m in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
            segments.append((re.sub(r"\s+", " ", m.group(1)).strip(), text[m.start():end].strip()))
    else:
        segments.append((None, text))

    out = []
    for madde, seg in segments:
        for piece in _pack(seg):
            head = f"{baslik} – {madde}" if madde else baslik
            out.append({"madde": madde, "icerik": f"{head}\n{piece}"})
    return out