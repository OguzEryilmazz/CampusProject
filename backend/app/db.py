"""Supabase PostgREST istemcisi (service_role anahtarıyla, yalnızca backend)."""
from datetime import datetime, timezone

import httpx


class Db:
    def __init__(self, url, key, http=None):
        self.base = f"{url}/rest/v1"
        self.http = http or httpx.AsyncClient(timeout=15)
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    async def _get(self, table, params):
        r = await self.http.get(f"{self.base}/{table}", params=params, headers=self.headers)
        r.raise_for_status()
        return r.json()

    async def schedule_today(self, gun):
        return await self._get("schedule_items",
                               {"gun": f"eq.{gun}", "select": "user_id,baslangic,bitis"})

    async def favorite_stops(self, user_ids):
        return await self._get("favorite_stops", {
            "user_id": f"in.({','.join(user_ids)})",
            "select": "user_id,durak_no,ad,bildirim_dk",
        })

    async def profiles(self, user_ids):
        """user_id -> {"kampus": ..., "bildirim_acik": ...}"""
        rows = await self._get("profiles", {
            "id": f"in.({','.join(user_ids)})", "select": "id,kampus,bildirim_acik"})
        return {r["id"]: {"kampus": r["kampus"], "bildirim_acik": r["bildirim_acik"]} for r in rows}

    async def campus_lines(self, campuses):
        """kampüs adı -> o kampüse hizmet veren hat_no kümesi (bizim tanımladığımız liste)."""
        quoted = ",".join('"' + c.replace('"', '\\"') + '"' for c in campuses)
        rows = await self._get("campus_lines", {"kampus": f"in.({quoted})", "select": "kampus,hat_no"})
        out = {}
        for r in rows:
            out.setdefault(r["kampus"], set()).add(r["hat_no"])
        return out

    async def recent_notifications(self, user_ids, since):
        """(user_id, durak_no) -> yakın zamanda bildirilen arac_no kümesi."""
        since_utc = since.astimezone(timezone.utc).isoformat()
        rows = await self._get("notifications", {
            "user_id": f"in.({','.join(user_ids)})",
            "created_at": f"gte.{since_utc}",
            "select": "user_id,durak_no,araclar",
        })
        out = {}
        for r in rows:
            kume = out.setdefault((r["user_id"], r["durak_no"]), set())
            kume.update(a["arac_no"] for a in (r.get("araclar") or []))
        return out

    async def insert_notification(self, n):
        """Bildirimi kaydeder, oluşan satırın id'sini döndürür."""
        r = await self.http.post(f"{self.base}/notifications", json=n,
                                 headers={**self.headers, "Prefer": "return=representation"})
        r.raise_for_status()
        rows = r.json()
        return rows[0]["id"] if rows else None

    async def mark_sent(self, notification_id, when=None):
        when = when or datetime.now(timezone.utc)
        r = await self.http.patch(f"{self.base}/notifications", params={"id": f"eq.{notification_id}"},
                                  json={"sent_at": when.astimezone(timezone.utc).isoformat()},
                                  headers=self.headers)
        r.raise_for_status()

    async def tokens_of(self, user_id):
        rows = await self._get("device_tokens", {"user_id": f"eq.{user_id}", "select": "token"})
        return [r["token"] for r in rows]

    async def upsert_device(self, user_id, token, platform):
        r = await self.http.post(
            f"{self.base}/device_tokens", params={"on_conflict": "token"},
            json={"user_id": user_id, "token": token, "platform": platform,
                  "last_seen": datetime.now(timezone.utc).isoformat()},
            headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"})
        r.raise_for_status()

    async def delete_device(self, token, user_id=None):
        params = {"token": f"eq.{token}"}
        if user_id:  # istemciden gelen silmede yalnızca kendi cihazı
            params["user_id"] = f"eq.{user_id}"
        r = await self.http.delete(f"{self.base}/device_tokens", params=params, headers=self.headers)
        r.raise_for_status()


    # ---- Kullanıcıya dönük okumalar ----
    async def profile_of(self, user_id):
        rows = await self._get("profiles", {
            "id": f"eq.{user_id}", "select": "ad,rol,fakulte,kampus,bildirim_acik"})
        return rows[0] if rows else None

    async def favorite_stops_of(self, user_id):
        return await self._get("favorite_stops", {
            "user_id": f"eq.{user_id}", "select": "id,durak_no,ad,bildirim_dk", "order": "created_at.asc"})

    async def notifications_of(self, user_id, limit=20):
        return await self._get("notifications", {
            "user_id": f"eq.{user_id}", "order": "created_at.desc", "limit": str(limit),
            "select": "id,durak_no,mesaj,dakika,araclar,created_at,sent_at"})

    # ---- RAG ----
    @staticmethod
    def _vec(v):
        return v if isinstance(v, str) else "[" + ",".join(f"{x:.6f}" for x in v) + "]"

    async def get_document(self, kaynak_id):
        rows = await self._get("documents", {"kaynak_id": f"eq.{kaynak_id}", "select": "id,icerik_hash"})
        return rows[0] if rows else None

    async def upsert_document(self, doc):
        r = await self.http.post(f"{self.base}/documents", params={"on_conflict": "kaynak_id"}, json=doc,
                                 headers={**self.headers,
                                          "Prefer": "resolution=merge-duplicates,return=representation"})
        r.raise_for_status()
        return r.json()[0]["id"]

    async def delete_chunks(self, document_id):
        r = await self.http.delete(f"{self.base}/doc_chunks", params={"document_id": f"eq.{document_id}"},
                                   headers=self.headers)
        r.raise_for_status()

    async def insert_chunks(self, rows, batch=100):
        for i in range(0, len(rows), batch):
            r = await self.http.post(f"{self.base}/doc_chunks", json=rows[i:i + batch],
                                     headers={**self.headers, "Prefer": "return=minimal"})
            r.raise_for_status()

    async def match_chunks(self, embedding, k, rol, fakulte):
        r = await self.http.post(f"{self.base}/rpc/match_chunks", headers=self.headers, json={
            "query_embedding": self._vec(embedding), "match_count": k,
            "p_rol": rol, "p_fakulte": fakulte})
        r.raise_for_status()
        return r.json()

    async def user_scope(self, user_id):
        """Giriş yapmış kullanıcının (rol, fakülte) bilgisi; profil yoksa (None, None)."""
        rows = await self._get("profiles", {"id": f"eq.{user_id}", "select": "rol,fakulte"})
        return (rows[0]["rol"], rows[0]["fakulte"]) if rows else (None, None)