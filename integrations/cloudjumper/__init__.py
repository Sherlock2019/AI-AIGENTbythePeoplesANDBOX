"""CloudJumper integration — the Production Factory bridge.

YES AI CAN finds the problem, builds the agent, validates the value and prepares
the evidence. CloudJumper designs, deploys, validates and transitions the
solution into governed production.

Phase A (this module) is deliberately one-way and file-based: a validated
candidate becomes a signed, checksummed handoff bundle that CloudJumper's upload
importer already accepts. Live API sync and webhooks are not implemented here
because CloudJumper today has no service-to-service credential and emits no
events — see docs/cloudjumper-integration-implementation-plan.md.
"""

import os

from . import client, identity, package, passport, readiness

__all__ = ["client", "identity", "package", "passport", "readiness", "is_enabled"]

# Copied from YesAIcancommunity-LAB — see SYNCED_FROM.txt. models.py is
# deliberately absent here: AI 4 the People submits bundles, it does not track
# production candidates in a database.


def is_enabled() -> bool:
    """Feature flag. Enabled by default in development."""
    return (os.getenv("CLOUDJUMPER_PRODUCTION_FACTORY_ENABLED", "1") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
