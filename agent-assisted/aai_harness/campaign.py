from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .paths import campaign_root, ensure_aai_layout
from .schemas import now_version, write_json


@dataclass(slots=True)
class CampaignState:
    schema: str = "aai-campaign.v1"
    campaign_id: str = field(default_factory=lambda: f"campaign-{now_version()}")
    definition: str = ""
    objective: str = "latency optimization"
    status: str = "initialized"
    current_parent_id: str = "baseline"
    rounds: list[dict] = field(default_factory=list)


def init_campaign(definition: str, campaign_id: str | None = None, objective: str = "latency optimization") -> Path:
    campaign_id = campaign_id or f"campaign-{now_version()}"
    ensure_aai_layout(definition, campaign_id)
    state = CampaignState(campaign_id=campaign_id, definition=definition, objective=objective)
    return write_json(campaign_root(campaign_id) / "campaign.json", state)


def write_round_prompt(
    campaign_id: str,
    round_id: str,
    parent_id: str,
    objective: str,
    constraints: list[str] | None = None,
) -> Path:
    """Create a narrow child-worker prompt for one bounded optimization round."""
    root = campaign_root(campaign_id)
    prompt_dir = root / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    constraints = constraints or [
        "Only edit solution/ unless a Mode 3 proposal is explicitly accepted.",
        "Do not edit evaluator scripts, reference data, workload traces, retained baselines, or scoring logic.",
        "Emit ITERATIONS.md, trajectory.json, result.json, diff.patch, stdout/stderr logs, and audit.json.",
        "Treat failed candidates as evidence; do not hide failures.",
    ]
    body = [
        f"# AAI Child Prompt: {round_id}",
        "",
        f"- Campaign: `{campaign_id}`",
        f"- Parent: `{parent_id}`",
        f"- Objective: {objective}",
        "",
        "## Constraints",
        "",
    ]
    body.extend(f"- {item}" for item in constraints)
    body.extend([
        "",
        "## Required Evidence",
        "",
        "- `ITERATIONS.md`: what was tried and why.",
        "- `trajectory.json`: structured attempts and outcomes.",
        "- `result.json`: AAI EvidenceRecord schema payload.",
        "- `diff.patch`: candidate diff against parent.",
        "- `audit.json`: protected-path and leakage self-check.",
        "",
        "## Promotion Rule",
        "",
        "A candidate is not promoted unless the Master Campaign gate accepts the evidence and the metric improves against the selected parent/baseline.",
    ])
    return (prompt_dir / f"{round_id}.md").write_text("\n".join(body) + "\n", encoding="utf-8") or (prompt_dir / f"{round_id}.md")
