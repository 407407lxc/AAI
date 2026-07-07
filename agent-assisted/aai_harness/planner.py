from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import archive_root, campaign_root
from .schemas import now_version, read_json, write_json
from .workflow import advance_workflow, load_workflow


@dataclass(slots=True)
class PlannedChild:
    child_id: str
    parent_id: str
    objective: str
    constraints: list[str] = field(default_factory=list)
    agent_backend: str = "codex"
    evaluator_mode: str = "modal-full"


@dataclass(slots=True)
class PlannerDecision:
    schema: str = "aai-planner-decision.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    definition: str = ""
    planner_backend: str = "rule"
    objective: str = "latency optimization"
    parent_id: str = "baseline"
    rationale: str = ""
    children: list[PlannedChild] = field(default_factory=list)
    memory_inputs: dict[str, str | None] = field(default_factory=dict)
    avoid_traps: list[str] = field(default_factory=list)
    next_action: str = "prepare_child"


def _read_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def _recent_traps(definition: str, limit: int = 8) -> list[str]:
    path = archive_root(definition) / "traps" / "TRAPS.md"
    if not path.exists():
        return []
    lines = [line.strip("- \n") for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    return [line for line in lines if line][:limit]


def _selected_parent(definition: str) -> str:
    selected = _read_if_exists(archive_root(definition) / "selected-parent.json")
    if not selected:
        return "baseline"
    value = selected.get("selected") or selected.get("parent_id") or selected.get("id")
    return str(value) if value else "baseline"


def propose_round(
    campaign_id: str,
    objective: str | None = None,
    child_id: str | None = None,
    num_children: int = 1,
    planner_backend: str | None = None,
    advance: bool = True,
) -> Path:
    """Write a LoongFlow-style structured planner decision for the next AAI round.

    This is intentionally a hard artifact, not just a prompt. The executor backend
    may receive a textual prompt later, but the workflow state machine consumes
    this structured plan.
    """
    workflow = load_workflow(campaign_id)
    root = campaign_root(campaign_id)
    plans_dir = root / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)

    definition = workflow.definition
    summary_json = root / "campaign_summary.json"
    memory_update_json = root / "memory_update.json"
    selected_parent = _selected_parent(definition)
    traps = _recent_traps(definition)
    objective = objective or workflow.objective
    planner_backend = planner_backend or workflow.planner_backend

    children: list[PlannedChild] = []
    version = now_version()
    for idx in range(num_children):
        cid = child_id or f"child-{version}-{idx + 1:02d}"
        children.append(
            PlannedChild(
                child_id=cid,
                parent_id=selected_parent,
                objective=objective,
                constraints=[
                    "edit only workspace/solution",
                    "do not edit evaluator, scoring, benchmark data, archive, or memory",
                    "record attempts in ITERATIONS.md / trajectory.json / audit.json",
                    "preserve correctness before latency promotion",
                ],
                agent_backend=workflow.executor_backend,
                evaluator_mode=workflow.evaluator_backend,
            )
        )

    decision = PlannerDecision(
        campaign_id=campaign_id,
        definition=definition,
        planner_backend=planner_backend,
        objective=objective,
        parent_id=selected_parent,
        rationale=(
            "Rule planner selected the current archive parent and emitted bounded child tasks. "
            "Future planner backends may replace this with LLM/LoongFlow-compatible strategic planning."
        ),
        children=children,
        memory_inputs={
            "campaign_summary_json": str(summary_json) if summary_json.exists() else None,
            "memory_update_json": str(memory_update_json) if memory_update_json.exists() else None,
            "traps_md": str(archive_root(definition) / "traps" / "TRAPS.md"),
            "selected_parent_json": str(archive_root(definition) / "selected-parent.json"),
        },
        avoid_traps=traps,
    )
    path = write_json(plans_dir / f"plan-{version}.json", decision)
    md_path = plans_dir / f"plan-{version}.md"
    md_path.write_text(render_plan_markdown(decision), encoding="utf-8")
    if advance:
        advance_workflow(
            campaign_id,
            "plan_round",
            artifacts={"plan_json": str(path), "plan_md": str(md_path)},
            notes=["Structured planner decision created."],
            parent_id=selected_parent,
            child_id=children[0].child_id if children else None,
        )
    return path


def render_plan_markdown(decision: PlannerDecision) -> str:
    lines = [
        f"# AAI Planner Decision: {decision.campaign_id}",
        "",
        f"- Version: `{decision.version}`",
        f"- Definition: `{decision.definition}`",
        f"- Planner backend: `{decision.planner_backend}`",
        f"- Parent: `{decision.parent_id}`",
        f"- Objective: {decision.objective}",
        "",
        "## Rationale",
        "",
        decision.rationale,
        "",
        "## Avoid traps",
        "",
    ]
    if decision.avoid_traps:
        lines.extend(f"- {trap}" for trap in decision.avoid_traps)
    else:
        lines.append("- none")
    lines.extend(["", "## Planned children", ""])
    for child in decision.children:
        lines.extend([
            f"### `{child.child_id}`",
            "",
            f"- Parent: `{child.parent_id}`",
            f"- Agent backend: `{child.agent_backend}`",
            f"- Evaluator mode: `{child.evaluator_mode}`",
            f"- Objective: {child.objective}",
            "- Constraints:",
        ])
        lines.extend(f"  - {constraint}" for constraint in child.constraints)
        lines.append("")
    return "\n".join(lines) + "\n"
