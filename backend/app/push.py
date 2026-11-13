"""FCM (HTTP v1) ile push bildirimi gönderimi. Yalnızca backend'de çalışır."""
import asyncio

import httpx

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushError(Exception):
    """Geçici/bilinmeyen FCM hatası (token silinmez, bildirim kaydı etkilenmez)."""


class FcmSender:
    def __init__(self, project_id, token_provider, http=None):
        self._url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        self._token_provider = token_provider   # async () -> OAuth erişim token'ı
        self._http = http or httpx.AsyncClient(timeout=15)

    async def send(self, token, title, body, data=None):
        """'ok' ya da 'invalid' (cihaz token'ı artık geçersiz) döner, diğer hatalarda PushError."""
        try:
            access = await self._token_provider()
            r = await self._http.post(
                self._url,
                headers={"Authorization": f"Bearer {access}"},
                json={"message": {
                    "token": token,
                    "notification": {"title": title, "body": body},
                    "data": {k: str(v) for k, v in (data or {}).items()},
                    "android": {"priority": "HIGH"},
                }},
            )
        except Exception as e:  # ağ, kimlik doğrulama vb.
            raise PushError(str(e)) from e
        if r.status_code == 200:
            return "ok"
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        codes = {d.get("errorCode") for d in err.get("details", []) if isinstance(d, dict)}
        if r.status_code == 404 or "UNREGISTERED" in codes:
            return "invalid"
        raise PushError(f"FCM {r.status_code}: {err.get('message') or r.text[:200]}")


def service_account_provider(path):
    """Hizmet hesabı JSON dosyasından (proje kimliği, erişim token'ı sağlayıcı) üretir."""
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(path, scopes=[SCOPE])

    async def provider():
        if not creds.valid:
            await asyncio.to_thread(creds.refresh, Request())
        return creds.token

    return creds.project_id, provider