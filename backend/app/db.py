"""Supabase PostgREST istemcisi (service_role anahtarıyla, yalnızca backend)."""
from datetime import timezone

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
            "select": "user_id,durak_no,ad",
        })

    async def profile_campuses(self, user_ids):
        """user_id -> kampüs adı (profilde kampüs yoksa None)."""
        rows = await self._get("profiles", {
            "id": f"in.({','.join(user_ids)})", "select": "id,kampus"})
        return {r["id"]: r["kampus"] for r in rows}

    async def campus_lines(self, campuses):
        """kampüs adı -> o kampüse hizmet veren hat_no kümesi (bizim tanımladığımız liste)."""
        quoted = ",".join('"' + c.replace('"', '\\"') + '"' for c in campuses)
        rows = await self._get("campus_lines", {"kampus": f"in.({quoted})", "select": "kampus,hat_no"})
        out = {}
        for r in rows:
            out.setdefault(r["kampus"], set()).add(r["hat_no"])
        return out

    async def recent_notifications(self, user_ids, since):
        since_utc = since.astimezone(timezone.utc).isoformat()
        rows = await self._get("notifications", {
            "user_id": f"in.({','.join(user_ids)})",
            "created_at": f"gte.{since_utc}",
            "select": "user_id,durak_no",
        })
        return {(r["user_id"], r["durak_no"]) for r in rows}

    async def insert_notification(self, n):
        r = await self.http.post(f"{self.base}/notifications", json=n,
                                 headers={**self.headers, "Prefer": "return=minimal"})
        r.raise_for_status()