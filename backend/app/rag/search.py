async def search(db, embedder, query, rol, fakulte, k=5):
    """Kullanıcının rolüne ve fakültesine uygun parçaları arar.

    rol/fakulte, istemciden değil giriş yapmış kullanıcının profilinden gelir; filtre
    veritabanı fonksiyonunda (match_chunks) uygulanır. Profil yoksa yalnızca herkese açık içerik döner.
    """
    query = (query or "").strip()
    if not query:
        return []
    vec = (await embedder.embed([query], kind="query"))[0]
    rows = await db.match_chunks(vec, k, rol, fakulte)
    return [{
        "icerik": r["icerik"], "baslik": r["baslik"], "madde": r.get("madde"),
        "kaynak_url": r.get("kaynak_url"), "score": round(float(r["score"]), 4),
    } for r in rows]