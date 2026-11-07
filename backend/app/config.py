import os
from urllib.parse import urlparse


def supabase_url():
    """https://xyz.supabase.co/rest/v1/ gibi yola sahip adreslerden yalnızca kökü alır."""
    url = os.environ.get("SUPABASE_URL")
    if not url:
        return None
    p = urlparse(url.strip())
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else None


def supabase_anon_key():
    return os.environ.get("SUPABASE_ANON_KEY")


def service_role_key():
    """YALNIZCA backend'de kullanılır (RLS'yi aşar). İstemciye ya da /config'e asla verilmez."""
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")