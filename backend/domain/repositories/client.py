import threading

from supabase import Client, create_client

from settings import SupabaseSettings

_sb_client: Client | None = None
_sb_lock = threading.Lock()


def get_supabase() -> Client | None:
    global _sb_client
    if _sb_client is not None:
        return _sb_client
    with _sb_lock:
        if _sb_client is not None:
            return _sb_client
        credentials = SupabaseSettings.from_environment().credentials
        if credentials is None:
            return None
        url, key = credentials
        _sb_client = create_client(url, key)
        return _sb_client
