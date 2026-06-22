"""Supabase client singleton.

One process, one client. Bound to the schema named in StorageConfig (typically
agents_dev or agents_prod) so downstream callers can do
client.table("agent_runs") without thinking about search_path.

The service-role key is required. RLS is bypassed; this code only runs from
the agent's own controlled environment, never from anywhere user-facing.
"""

from __future__ import annotations

from supabase import Client, create_client
from supabase.client import ClientOptions

from shared.config import StorageConfig

_client: Client | None = None
_bound_schema: str | None = None


def get_client(storage: StorageConfig) -> Client:
    """Return the process-wide Supabase client bound to storage.schema.

    First call constructs it. Subsequent calls return the same instance,
    provided the schema has not changed. A schema change mid-process means
    something is wrong upstream, so we fail loudly rather than silently
    rebuilding against a different target.
    """
    global _client, _bound_schema

    if _client is not None:
        if _bound_schema != storage.schema:
            raise RuntimeError(
                f"Supabase client already bound to schema {_bound_schema!r}, "
                f"refusing to rebind to {storage.schema!r} mid-process."
            )
        return _client

    _client = create_client(
        storage.supabase_url,
        storage.supabase_service_role_key,
        options=ClientOptions(schema=storage.schema),
    )
    _bound_schema = storage.schema
    return _client


def reset_client() -> None:
    """Drop the cached client. For tests only."""
    global _client, _bound_schema
    _client = None
    _bound_schema = None
