"""Shared agent configuration.

Config types that belong to the platform spine, not to any single agent.
StorageConfig lives here because the shared Supabase client (shared/db/client.py)
needs it, and every kl-agent that writes to the shared backend needs it too.
Putting it here keeps the hard invariant intact: shared/ never imports from
agents/.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Connection settings for the shared Supabase backend.

    schema is typically 'agents_dev' or 'agents_prod'. The service-role key
    bypasses RLS; it only ever runs from an agent's own controlled environment.
    """

    supabase_url: str
    supabase_service_role_key: str
    schema: str
