from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import campaign_root, resolve_artifact_path, workflow_path
from .schemas import AAI_SCHEMA, CampaignRecord, CampaignState, TransitionSpec, WorkflowEvent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


DEFAULT_TRANSITIONS: tuple[TransitionSpec, ...] = (
    TransitionSpec(
        action="parse_requirements",
        source=CampaignState.REQUEST_RECEIVED,
        target=CampaignState.REQUIREMENTS_PARSED,
        required_artifacts=("requirements",),
        description="Parse user demand into model, runtime, hardware, metrics, gates, dependencies, and credential policy.",
    ),
    TransitionSpec(
        action="need_bootstrap",
        source=CampaignState.REQUIREMENTS_PARSED,
        target=CampaignState.BOOTSTRAP_NEEDED,
        description="No valid deployment/baseline exists; enter Mode 0 bootstrap.",
    ),
    TransitionSpec(
        action="use_existing_baseline",
        source=CampaignState.REQUIREMENTS_PARSED,
        target=CampaignState.CAMPAIGN_READY,
        required_artifacts=("baseline_result",),
        description="A valid deployment and baseline already exist; enter Master Campaign.",
    ),
    TransitionSpec(
        action="identify_missing_parts",
        source=CampaignState.BOOTSTRAP_NEEDED,
        target=CampaignState.BOOTSTRAP_SCOPED,
        required_artifacts=("gap_report",),
        description="Identify missing model, environment, service, adapter, evaluator, and baseline components.",
    ),
    TransitionSpec(
        action="create_bootstrap_assets",
        source=CampaignState.BOOTSTRAP_SCOPED,
        target=CampaignState.BOOTSTRAP_BUILT,
        required_artifacts=("bootstrap_manifest",),
        description="Create installation/start scripts, health checks, and evaluator adapters.",
    ),
    TransitionSpec(
        action="run_health_check",
        source=CampaignState.BOOTSTRAP_BUILT,
        target=CampaignState.HEALTH_CHECKED,
        required_artifacts=("health_check",),
        description="Run deployment health checks.",
    ),
    TransitionSpec(
        action="run_baseline",
        source=CampaignState.HEALTH_CHECKED,
        target=CampaignState.BASELINE_EVALUATED,
        required_artifacts=("baseline_result",),
        description="Run bootstrap baseline evaluation.",
    ),
    TransitionSpec(
        action="accept_baseline",
        source=CampaignState.BASELINE_EVALUATED,
        target=CampaignState.CAMPAIGN_READY,
        required_artifacts=("baseline_result",),
        human_review_required=True,
        description="Accept a valid baseline and enter Master Campaign.",
    ),
    TransitionSpec(
        action="revise_bootstrap",
        source=CampaignState.BASELINE_EVALUATED,
        target=CampaignState.BOOTSTRAP_SCOPED,
        required_artifacts=("failure_path",),
        description="Reject invalid baseline and revise bootstrap scope.",
    ),
    TransitionSpec(
        action="select_parent",
        source=CampaignState.CAMPAIGN_READY,
        target=CampaignState.PARENT_SELECTED,
        required_artifacts=("reference_archive", "parent_selection"),
        description="Read archive and select seed or archived variant parent.",
    ),
    TransitionSpec(
        action="plan_round",
        source=CampaignState.PARENT_SELECTED,
        target=CampaignState.ROUND_PLANNED,
        required_artifacts=("round_prompt",),
        description="Write a narrow search prompt for this round.",
    ),
    TransitionSpec(
        action="spawn_child",
        source=CampaignState.ROUND_PLANNED,
        target=CampaignState.CHILD_RUNNING,
        required_artifacts=("child_runtime_spec",),
        runtime_may_execute=True,
        description="Spawn a bounded child workspace and run a worker runtime such as LoongFlow or Codex.",
    ),
    TransitionSpec(
        action="collect_child_evidence",
        source=CampaignState.CHILD_RUNNING,
        target=CampaignState.CHILD_EVIDENCE_READY,
        required_artifacts=("iterations", "trajectory", "result", "diff", "logs"),
        description="Collect child evidence bundle: iterations, trajectory, result, diff, logs.",
    ),
    TransitionSpec(
        action="prearchive_check",
        source=CampaignState.CHILD_EVIDENCE_READY,
        target=CampaignState.PREARCHIVE_CHECKED,
        required_artifacts=("audit_findings",),
        description="Check no evaluation leakage, no hard-coded answers, no baseline/scoring tampering, and gates passed.",
    ),
    TransitionSpec(
        action="archive_variant",
        source=CampaignState.PREARCHIVE_CHECKED,
        target=CampaignState.VARIANT_ARCHIVED,
        required_artifacts=("solution", "config", "result", "summary", "parent"),
        human_review_required=True,
        description="Archive a valuable passing variant.",
    ),
    TransitionSpec(
        action="archive_failed",
        source=CampaignState.PREARCHIVE_CHECKED,
        target=CampaignState.FAILED_ARCHIVED,
        required_artifacts=("failure_reason", "logs"),
        description="Archive failed/no-archive run with reason, logs, and transcript.",
    ),
    TransitionSpec(
        action="update_memory",
        source=CampaignState.VARIANT_ARCHIVED,
        target=CampaignState.MEMORY_UPDATED,
        required_artifacts=("memory_update", "harness_ledger"),
        description="Update long-term memory, traps, and harness ledger.",
    ),
    TransitionSpec(
        action="update_memory",
        source=CampaignState.FAILED_ARCHIVED,
        target=CampaignState.MEMORY_UPDATED,
        required_artifacts=("memory_update", "harness_ledger"),
        description="Update long-term memory from a failed/no-archive run.",
    ),
    TransitionSpec(
        action="write_proposal",
        source=CampaignState.MEMORY_UPDATED,
        target=CampaignState.PROPOSAL_WRITTEN,
        required_artifacts=("proposal",),
        description="Write a Mode 3 proposal describing evidence-backed harness/tooling gaps.",
    ),
    TransitionSpec(
        action="review_proposal",
        source=CampaignState.PROPOSAL_WRITTEN,
        target=CampaignState.PROPOSAL_REVIEWED,
        required_artifacts=("proposal_review",),
        human_review_required=True,
        description="Master/human reviews proposal; rejects scope freeze, generic knowledge, or unevidenced changes.",
    ),
    TransitionSpec(
        action="continue_campaign",
        source=CampaignState.PROPOSAL_REVIEWED,
        target=CampaignState.CAMPAIGN_READY,
        human_review_required=True,
        description="Continue campaign after proposal review.",
    ),
    TransitionSpec(
        action="continue_campaign",
        source=CampaignState.MEMORY_UPDATED,
        target=CampaignState.CAMPAIGN_READY,
        description="Continue campaign without Mode 3 change.",
    ),
    TransitionSpec(
        action="complete",
        source=CampaignState.MEMORY_UPDATED,
        target=CampaignState.COMPLETED,
        human_review_required=True,
        description="Stop the campaign.",
    ),
)


def transition_index() -> dict[tuple[str, str], TransitionSpec]:
    return {(str(t.source.value), t.action): t for t in DEFAULT_TRANSITIONS}


def init_campaign(campaign_id: str, objective: str, root: str | Path | None = None) -> Path:
    path = workflow_path(campaign_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = CampaignRecord(
        schema=AAI_SCHEMA,
        campaign_id=campaign_id,
        objective=objective,
        state=CampaignState.REQUEST_RECEIVED.value,
    )
    path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def load_campaign(campaign_id: str, root: str | Path | None = None) -> dict[str, Any]:
    path = workflow_path(campaign_id, root)
    if not path.exists():
        raise FileNotFoundError(f"Campaign workflow not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_campaign(campaign_id: str, record: dict[str, Any], root: str | Path | None = None) -> Path:
    path = workflow_path(campaign_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _normalize_artifacts(artifacts: dict[str, str] | None) -> dict[str, str]:
    return {str(k): str(v) for k, v in (artifacts or {}).items() if v is not None}


def _missing_required_artifacts(
    required: tuple[str, ...],
    existing: dict[str, str],
    provided: dict[str, str],
) -> list[str]:
    merged = {**existing, **provided}
    return [name for name in required if not merged.get(name)]


def _missing_artifact_files(artifacts: dict[str, str], root: str | Path | None = None) -> dict[str, str]:
    missing: dict[str, str] = {}
    for name, path in artifacts.items():
        resolved = resolve_artifact_path(path, root)
        if not resolved.exists():
            missing[name] = str(resolved)
    return missing


def allowed_actions(campaign_id: str, root: str | Path | None = None) -> list[str]:
    record = load_campaign(campaign_id, root)
    state = record["state"]
    return [t.action for t in DEFAULT_TRANSITIONS if t.source.value == state]


def advance_campaign(
    campaign_id: str,
    action: str,
    artifacts: dict[str, str] | None = None,
    notes: str = "",
    actor: str = "human",
    root: str | Path | None = None,
    require_existing_files: bool = True,
) -> Path:
    record = load_campaign(campaign_id, root)
    state = record["state"]
    spec = transition_index().get((state, action))
    if spec is None:
        allowed = allowed_actions(campaign_id, root)
        raise ValueError(f"Action {action!r} is not allowed from {state}. Allowed: {allowed}")

    if spec.human_review_required and actor == "runtime":
        raise PermissionError(f"Action {action!r} requires human/master review and cannot be advanced by a runtime.")

    provided = _normalize_artifacts(artifacts)
    existing = dict(record.get("artifacts", {}))
    missing_required = _missing_required_artifacts(spec.required_artifacts, existing, provided)
    if missing_required:
        raise ValueError(f"Missing required artifact names for {action!r}: {missing_required}")

    if require_existing_files:
        missing_files = _missing_artifact_files(provided, root)
        if missing_files:
            raise FileNotFoundError(f"Artifact path(s) do not exist: {missing_files}")

    event = WorkflowEvent(
        timestamp=utc_now(),
        action=action,
        source=state,
        target=spec.target.value,
        actor=actor,
        artifacts=provided,
        notes=notes,
    )
    record.setdefault("events", []).append(asdict(event))
    record.setdefault("artifacts", {}).update(provided)
    record["state"] = spec.target.value

    return save_campaign(campaign_id, record, root)


def export_contract() -> list[dict[str, Any]]:
    return [
        {
            "action": t.action,
            "source": t.source.value,
            "target": t.target.value,
            "required_artifacts": list(t.required_artifacts),
            "runtime_may_execute": t.runtime_may_execute,
            "human_review_required": t.human_review_required,
            "description": t.description,
        }
        for t in DEFAULT_TRANSITIONS
    ]


def ensure_campaign_dirs(campaign_id: str, root: str | Path | None = None) -> Path:
    base = campaign_root(campaign_id, root)
    for sub in ("artifacts", "runtime", "traces", "archive", "memory", "proposals"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base
