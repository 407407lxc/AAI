"""AAI agentic infrastructure harness.

AAI is the external workflow and governance layer around phase-local
agent runtimes such as LoongFlow, Codex, manual runners, or future backends.
"""

from .schemas import AAI_SCHEMA, CampaignState
from .workflow import advance_campaign, init_campaign, load_campaign

__all__ = [
    "AAI_SCHEMA",
    "CampaignState",
    "init_campaign",
    "advance_campaign",
    "load_campaign",
]
