from supabase import Client


def _first(data: list[dict]):
    if not data:
        raise ValueError("no rows returned")
    return data[0]


class _Repo:
    def __init__(self, client: Client, table: str):
        self.client = client
        self.table = table
