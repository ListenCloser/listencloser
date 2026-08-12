import os

import pytest
from supabase import create_client


@pytest.fixture(scope="session")
def sb():
    """A service-role Supabase client for the disposable integration database.

    Skipped unless SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set, which the
    database-integration CI job provides via `supabase status -o env`.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set; "
            "run via the database-integration CI job"
        )
    return create_client(url, key)
