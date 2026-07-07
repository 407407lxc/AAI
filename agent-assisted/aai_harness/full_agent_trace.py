from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import archive_root, campaign_root
from .schemas import now_version, read_json, write_json
from .workspace import child_root


@dataclass(slots=True)
class TracePhase:
    name: str
    path: str
    artifacts: dict[str, str | None] = field(default_factory=dict)


@dataclass(slots=True)
class FullAgentTraceIndex:
    schema: str = "aai-full-agent-trace.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    definition: str = ""
    iteration: int = 0
    child_id: str | None = None
    trace_root: str = ""
    phases: list[TracePhase] = field(default_factory=list)
    checkpoint_path: str | None = None
    notes: list[str] = field(default_factory=list)


def trace_root(campaign_id: str) -> Path:
    return campaign_root(campaign_id) / "full_agent_trace"


def iteration_root(campaign_id: str, iteration: int) -> Path:
    return trace_root(campaign_id) / "iteration" / str(iteration)


def evaluator_root(campaign_id: str, child_id: str, iteration: int) -> Path:
    raw = f"{campaign_id}:{child_id}:{iteration}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:10]
    return trace_root(campaign_id) / "evaluator" / f"eval_{digest}"


def checkpoint_root(campaign_id: str, iteration: int, child_id: str | None = None) -> Path:
    suffix = child_id or "checkpoint"
    return trace_root(campaign_id) / "database" / "checkpoints" / f"checkpoint-iter-{iteration}-{suffix}"


def _copy_file(src: Path | None, dst: Path) -> str | None:
    if not src or not src.exists() or not src.is_file():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def _copy_tree(src: Path | None, dst: Path) -> str | None:
    if not src or not src.exists() or not src.is_dir():
        return None
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    return str(dst)


def _latest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _latest_glob(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    return _latest(list(root.glob(pattern)))


def init_full_agent_trace(campaign_id: str, definition: str, objective: str | None = None) -> Path:
    """Create an AAI trace tree that mirrors the original full-agent layout.

    The original full-agent package preserved planner / executor / evaluator /
    summarizer I/O plus checkpoints. This function creates the same top-level
    shape for AAI campaigns without vendoring the historical full-agent traces.
    """
    root = trace_root(campaign_id)
    for subdir in [
        root / "database" / "checkpoints",
        root / "database" / "solutions",
        root / "iteration",
        root / "evaluator",
    ]:
        subdir.mkdir(parents=True, exist_ok=True)
    index = FullAgentTraceIndex(
        campaign_id=campaign_id,
        definition=definition,
        trace_root=str(root),
        notes=[
            "AAI full-agent-style trace initialized.",
            "This mirrors the original full-agent trace schema but uses AAI workflow artifacts.",
        ],
    )
    if objective:
        index.notes.append(f"Objective: {objective}")
    return write_json(root / "trace_index.json", index)


def _copy_planner_phase(campaign_id: str, iteration: int) -> TracePhase:
    root = campaign_root(campaign_id)
    phase_dir = iteration_root(campaign_id, iteration) / "planner"
    plan_json = _latest_glob(root / "plans", "plan-*.json")
    plan_md = _latest_glob(root / "plans", "plan-*.md")
    artifacts = {
        "plan_json": _copy_file(plan_json, phase_dir / "plan.json"),
        "plan_md": _copy_file(plan_md, phase_dir / "plan.md"),
    }
    return TracePhase(name="planner", path=str(phase_dir), artifacts=artifacts)


def _copy_executor_phase(campaign_id: str, iteration: int, child_id: str) -> TracePhase:
    child = child_root(campaign_id, child_id)
    phase_dir = iteration_root(campaign_id, iteration) / "executor" / child_id
    artifacts = {
        "child_json": _copy_file(child / "child.json", phase_dir / "child.json"),
        "codex_prompt": _copy_file(child / "codex_prompt.md", phase_dir / "prompt.md"),
        "agent_run_json": _copy_file(child / "codex_agent_run.json", phase_dir / "agent_run.json"),
        "iterations_md": _copy_file(child / "ITERATIONS.md", phase_dir / "ITERATIONS.md"),
        "trajectory_json": _copy_file(child / "trajectory.json", phase_dir / "trajectory.json"),
        "audit_json": _copy_file(child / "audit.json", phase_dir / "audit.json"),
        "diff_patch": _copy_file(child / "diff.patch", phase_dir / "diff.patch"),
        "workspace_solution": _copy_tree(child / "workspace" / "solution", phase_dir / "candidate_solution"),
    }
    return TracePhase(name="executor", path=str(phase_dir), artifacts=artifacts)


def _copy_evaluator_phase(campaign_id: str, iteration: int, child_id: str) -> TracePhase:
    child = child_root(campaign_id, child_id)
    phase_dir = evaluator_root(campaign_id, child_id, iteration)
    artifacts = {
        "child_eval_json": _copy_file(child / "child_eval.json", phase_dir / "child_eval.json"),
        "result_json": _copy_file(child / "result.json", phase_dir / "result.json"),
        "round_report_json": _copy_file(child / "round_report.json", phase_dir / "round_report.json"),
        "gate_json": _copy_file(child / "gate.json", phase_dir / "gate.json"),
        "solution_json": _copy_file(child / "solution.json", phase_dir / "solution.json"),
        "benchmark_detailed_results": _copy_file(child / "benchmark_detailed_results.json", phase_dir / "benchmark_detailed_results.json"),
        "retained_run_log": _copy_file(child / "retained_run.log", phase_dir / "evaluation_process.log"),
        "logs": _copy_tree(child / "logs", phase_dir / "logs"),
    }
    return TracePhase(name="evaluator", path=str(phase_dir), artifacts=artifacts)


def _copy_summarizer_phase(campaign_id: str, iteration: int) -> TracePhase:
    root = campaign_root(campaign_id)
    phase_dir = iteration_root(campaign_id, iteration) / "summarizer"
    artifacts = {
        "campaign_summary_json": _copy_file(root / "campaign_summary.json", phase_dir / "campaign_summary.json"),
        "campaign_summary_md": _copy_file(root / "campaign_summary.md", phase_dir / "summary.md"),
        "memory_update_json": _copy_file(root / "memory_update.json", phase_dir / "memory_update.json"),
        "workflow_json": _copy_file(root / "workflow.json", phase_dir / "workflow.json"),
    }
    return TracePhase(name="summarizer", path=str(phase_dir), artifacts=artifacts)


def _write_checkpoint(campaign_id: str, definition: str, iteration: int, child_id: str | None) -> str:
    ckpt = checkpoint_root(campaign_id, iteration, child_id)
    ckpt.mkdir(parents=True, exist_ok=True)
    child = child_root(campaign_id, child_id) if child_id else None
    population_json = archive_root(definition) / "population" / "population.json"
    selected_parent_json = archive_root(definition) / "selected-parent.json"
    artifacts = {
        "population": _copy_file(population_json, ckpt / "metadata.json"),
        "selected_parent": _copy_file(selected_parent_json, ckpt / "selected-parent.json"),
        "best_solution_tree": _copy_tree(child / "workspace" / "solution" if child else None, ckpt / "best_solution"),
        "best_solution_evidence": _copy_file(child / "result.json" if child else None, ckpt / "best_solution.json"),
        "round_report": _copy_file(child / "round_report.json" if child else None, ckpt / "round_report.json"),
    }
    checkpoint_record = {
        "schema": "aai-full-agent-checkpoint.v1",
        "version": now_version(),
        "campaign_id": campaign_id,
        "definition": definition,
        "iteration": iteration,
        "child_id": child_id,
        "artifacts": artifacts,
    }
    write_json(ckpt / "checkpoint.json", checkpoint_record)
    return str(ckpt)


def sync_full_agent_trace(
    campaign_id: str,
    definition: str,
    iteration: int,
    child_id: str | None = None,
) -> Path:
    """Mirror current AAI artifacts into a full-agent-style trace tree.

    This gives future agents a familiar LoongFlow-like trace layout while keeping
    AAI's own workflow, evidence, gates, and memory as the source of truth.
    """
    init_full_agent_trace(campaign_id, definition)
    phases: list[TracePhase] = [_copy_planner_phase(campaign_id, iteration)]
    if child_id:
        phases.append(_copy_executor_phase(campaign_id, iteration, child_id))
        phases.append(_copy_evaluator_phase(campaign_id, iteration, child_id))
    phases.append(_copy_summarizer_phase(campaign_id, iteration))
    ckpt = _write_checkpoint(campaign_id, definition, iteration, child_id)
    index = FullAgentTraceIndex(
        campaign_id=campaign_id,
        definition=definition,
        iteration=iteration,
        child_id=child_id,
        trace_root=str(trace_root(campaign_id)),
        phases=phases,
        checkpoint_path=ckpt,
        notes=[
            "AAI artifacts mirrored into LoongFlow/full-agent-style trace layout.",
            "AAI workflow.json remains the authoritative control artifact.",
        ],
    )
    return write_json(trace_root(campaign_id) / "trace_index.json", index)


def trace_status(campaign_id: str) -> dict[str, Any]:
    path = trace_root(campaign_id) / "trace_index.json"
    if not path.exists():
        return {"campaign_id": campaign_id, "exists": False, "trace_root": str(trace_root(campaign_id))}
    data = read_json(path)
    data["exists"] = True
    return data


def render_trace_tree(campaign_id: str) -> str:
    root = trace_root(campaign_id)
    if not root.exists():
        return f"Trace does not exist: {root}\n"
    lines = [str(root)]
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        depth = len(rel.parts)
        prefix = "  " * depth
        lines.append(f"{prefix}{rel.name}{'/' if path.is_dir() else ''}")
    return "\n".join(lines) + "\n"
