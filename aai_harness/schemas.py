from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

AAI_SCHEMA = "aai-workflow-contract.v0"


class CampaignState(str, Enum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    REQUIREMENTS_PARSED = "REQUIREMENTS_PARSED"

    BOOTSTRAP_NEEDED = "BOOTSTRAP_NEEDED"
    BOOTSTRAP_SCOPED = "BOOTSTRAP_SCOPED"
    BOOTSTRAP_BUILT = "BOOTSTRAP_BUILT"
    HEALTH_CHECKED = "HEALTH_CHECKED"
    BASELINE_EVALUATED = "BASELINE_EVALUATED"

    CAMPAIGN_READY = "CAMPAIGN_READY"
    PARENT_SELECTED = "PARENT_SELECTED"
    ROUND_PLANNED = "ROUND_PLANNED"

    CHILD_RUNNING = "CHILD_RUNNING"
    CHILD_EVIDENCE_READY = "CHILD_EVIDENCE_READY"
    PREARCHIVE_CHECKED = "PREARCHIVE_CHECKED"

    VARIANT_ARCHIVED = "VARIANT_ARCHIVED"
    FAILED_ARCHIVED = "FAILED_ARCHIVED"
    MEMORY_UPDATED = "MEMORY_UPDATED"

    PROPOSAL_WRITTEN = "PROPOSAL_WRITTEN"
    PROPOSAL_REVIEWED = "PROPOSAL_REVIEWED"

    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ArtifactRef:
    name: str
    path: str
    kind: str = "file"
    description: str = ""


@dataclass(frozen=True)
class TransitionSpec:
    action: str
    source: CampaignState
    target: CampaignState
    required_artifacts: tuple[str, ...] = ()
    description: str = ""
    runtime_may_execute: bool = False
    human_review_required: bool = False


@dataclass
class WorkflowEvent:
    timestamp: str
    action: str
    source: str
    target: str
    actor: str = "human"
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class CampaignRecord:
    schema: str
    campaign_id: str
    objective: str
    state: str
    artifacts: dict[str, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
