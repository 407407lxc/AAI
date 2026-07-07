from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .paths import campaign_root
from .schemas import now_version, read_json, write_json

WorkflowState = Literal[
    "TASK_RESOLVED",
    "BASELINE_READY",
    "ROUND_PLANNED",
    "CHILD_PREPARED",
    "AGENT_RAN",
    "EVALUATED",
    "GATED_ARCHIVED",
    "SUMMARIZED",
    "MEMORY_UPDATED",
    "PARENT_SELECTED",
    "PROPOSAL_REVIEW",
]

WorkflowAction = Literal[
    "bootstrap_baseline",
    "plan_round",
    "prepare_child",
    "run_agent",
    "evaluate_child",
    "gate_archive",
    "summarize_campaign",
    "update_memory",
    "select_parent",
    "review_proposal",
]


@dataclass(slots=True)
class WorkflowTransition:
    action: WorkflowAction
    from_state: WorkflowState
    to_state: WorkflowState
    required_artifacts: list[str] = field(default_factory=list)
    produced_artifacts: list[str] = field(default_factory=list)
    description: str = ""


@dataclass(slots=True)
class WorkflowEvent:
    version: str
    action: WorkflowAction
    from_state: WorkflowState
    to_state: WorkflowState
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WorkflowSpec:
    schema: str = "aai-workflow.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    definition: str = ""
    config_path: str = ""
    objective: str = "latency optimization"
    current_state: WorkflowState = "TASK_RESOLVED"
    planner_backend: str = "rule"
    executor_backend: str = "codex"
    evaluator_backend: str = "modal-full"
    child_id: str | None = None
    parent_id: str = "baseline"
    transitions: list[WorkflowTransition] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)


DEFAULT_TRANSITIONS: list[WorkflowTransition] = [
    WorkflowTransition(
        action="bootstrap_baseline",
        from_state="TASK_RESOLVED",
        to_state="BASELINE_READY",
        produced_artifacts=["baseline_manifest"],
        description="Mode 0 bootstrap build / first baseline.",
    ),
    WorkflowTransition(
        action="plan_round",
        from_state="BASELINE_READY",
        to_state="ROUND_PLANNED",
        required_artifacts=["baseline_manifest"],
        produced_artifacts=["plan_json"],
        description="LoongFlow-style planner produces structured round plan.",
    ),
    WorkflowTransition(
        action="plan_round",
        from_state="PARENT_SELECTED",
        to_state="ROUND_PLANNED",
        required_artifacts=["selected_parent"],
        produced_artifacts=["plan_json"],
        description="Plan the next round from selected parent and campaign memory.",
    ),
    WorkflowTransition(
        action="prepare_child",
        from_state="ROUND_PLANNED",
        to_state="CHILD_PREPARED",
        required_artifacts=["plan_json"],
        produced_artifacts=["child_json"],
        description="Create isolated child workspace.",
    ),
    WorkflowTransition(
        action="run_agent",
        from_state="CHILD_PREPARED",
        to_state="AGENT_RAN",
        required_artifacts=["child_json"],
        produced_artifacts=["agent_run_json"],
        description="Executor backend, such as Codex, edits only child workspace/solution.",
    ),
    WorkflowTransition(
        action="evaluate_child",
        from_state="AGENT_RAN",
        to_state="EVALUATED",
        required_artifacts=["agent_run_json"],
        produced_artifacts=["child_eval_json", "result_json", "diff_patch"],
        description="Run evaluator backend and finalize child evidence.",
    ),
    WorkflowTransition(
        action="gate_archive",
        from_state="EVALUATED",
        to_state="GATED_ARCHIVED",
        required_artifacts=["result_json", "diff_patch"],
        produced_artifacts=["gate_json", "archive_manifest", "round_report"],
        description="Gate evidence and archive as variant or failed evidence.",
    ),
    WorkflowTransition(
        action="summarize_campaign",
        from_state="GATED_ARCHIVED",
        to_state="SUMMARIZED",
        required_artifacts=["round_report"],
        produced_artifacts=["campaign_summary_json", "campaign_summary_md"],
        description="Summarizer writes campaign rollup.",
    ),
    WorkflowTransition(
        action="update_memory",
        from_state="SUMMARIZED",
        to_state="MEMORY_UPDATED",
        required_artifacts=["campaign_summary_json"],
        produced_artifacts=["memory_update_json"],
        description="Append summary findings into harness-ledger and TRAPS.",
    ),
    WorkflowTransition(
        action="select_parent",
        from_state="MEMORY_UPDATED",
        to_state="PARENT_SELECTED",
        required_artifacts=["memory_update_json"],
        produced_artifacts=["selected_parent"],
        description="Select parent for the next round.",
    ),
    WorkflowTransition(
        action="review_proposal",
        from_state="MEMORY_UPDATED",
        to_state="PROPOSAL_REVIEW",
        produced_artifacts=["proposal_review"],
        description="Mode 3 evidence-backed harness proposal review.",
    ),
]

DEFAULT_INVARIANTS = [
    "AAI owns the workflow; agent backends may only execute bounded nodes.",
    "Child agents may edit only workspace/solution unless a Mode 3 proposal is accepted.",
    "Evaluator, benchmark data, scoring, archive, and memory are protected from child agents.",
    "Failed candidates are negative evidence and must be archived, not discarded.",
    "Promotion requires evidence, gate pass, and an archive manifest.",
]


def workflow_path(campaign_id: str) -> Path:
    return campaign_root(campaign_id) / "workflow.json"


def init_workflow(
    campaign_id: str,
    definition: str,
    config_path: str | Path,
    objective: str = "latency optimization",
    planner_backend: str = "rule",
    executor_backend: str = "codex",
    evaluator_backend: str = "modal-full",
    parent_id: str = "baseline",
) -> Path:
    spec = WorkflowSpec(
        campaign_id=campaign_id,
        definition=definition,
        config_path=str(config_path),
        objective=objective,
        planner_backend=planner_backend,
        executor_backend=executor_backend,
        evaluator_backend=evaluator_backend,
        parent_id=parent_id,
        transitions=DEFAULT_TRANSITIONS,
        invariants=DEFAULT_INVARIANTS,
    )
    return write_json(workflow_path(campaign_id), spec)


def load_workflow(campaign_id: str) -> WorkflowSpec:
    data = read_json(workflow_path(campaign_id))
    transitions = [WorkflowTransition(**item) for item in data.get("transitions", [])]
    events = [WorkflowEvent(**item) for item in data.get("events", [])]
    keep = {name for name in WorkflowSpec.__dataclass_fields__}
    payload = {k: v for k, v in data.items() if k in keep and k not in {"transitions", "events"}}
    return WorkflowSpec(**payload, transitions=transitions, events=events)


def allowed_transitions(spec: WorkflowSpec) -> list[WorkflowTransition]:
    return [transition for transition in spec.transitions if transition.from_state == spec.current_state]


def assert_can_transition(spec: WorkflowSpec, action: WorkflowAction) -> WorkflowTransition:
    matches = [transition for transition in allowed_transitions(spec) if transition.action == action]
    if not matches:
        allowed = ", ".join(t.action for t in allowed_transitions(spec)) or "none"
        raise ValueError(f"action {action!r} is not allowed from {spec.current_state}; allowed: {allowed}")
    return matches[0]


def advance_workflow(
    campaign_id: str,
    action: WorkflowAction,
    artifacts: dict[str, str] | None = None,
    notes: list[str] | None = None,
    child_id: str | None = None,
    parent_id: str | None = None,
) -> Path:
    spec = load_workflow(campaign_id)
    transition = assert_can_transition(spec, action)
    event = WorkflowEvent(
        version=now_version(),
        action=action,
        from_state=spec.current_state,
        to_state=transition.to_state,
        artifacts=artifacts or {},
        notes=notes or [],
    )
    spec.current_state = transition.to_state
    spec.events.append(event)
    if child_id:
        spec.child_id = child_id
    if parent_id:
        spec.parent_id = parent_id
    return write_json(workflow_path(campaign_id), spec)


def workflow_status(campaign_id: str) -> dict[str, Any]:
    spec = load_workflow(campaign_id)
    return {
        "campaign_id": spec.campaign_id,
        "definition": spec.definition,
        "current_state": spec.current_state,
        "planner_backend": spec.planner_backend,
        "executor_backend": spec.executor_backend,
        "evaluator_backend": spec.evaluator_backend,
        "parent_id": spec.parent_id,
        "child_id": spec.child_id,
        "allowed_actions": [t.action for t in allowed_transitions(spec)],
        "invariants": spec.invariants,
        "events": [asdict(event) for event in spec.events],
    }
