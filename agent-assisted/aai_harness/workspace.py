from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .bootstrap import resolve_task
from .diffing import capture_directory_diff
from .paths import campaign_root, ensure_aai_layout, resolve_project_path
from .schemas import ArtifactRefs, EvidenceRecord, Metrics, TaskSpec, now_version, read_json, write_json

REQUIRED_CHILD_FILES = [
    "ITERATIONS.md",
    "trajectory.json",
    "result.json",
    "diff.patch",
    "audit.json",
]


def child_root(campaign_id: str, child_id: str) -> Path:
    return campaign_root(campaign_id) / "children" / child_id


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def prepare_child_workspace(
    campaign_id: str,
    config_path: str | Path,
    child_id: str | None = None,
    solution_dir: str | Path | None = None,
    parent_id: str = "baseline",
    version: str | None = None,
) -> Path:
    """Create an isolated child workspace seeded from the selected parent solution.

    The workspace is under `.aai/campaigns/<campaign_id>/children/<child_id>/`.
    It contains both an immutable parent snapshot and a mutable candidate copy.
    Existing evaluator scripts can pack the candidate by using the absolute
    `workspace/config.toml` and `workspace/solution` paths recorded in
    `child.json`.
    """
    version = version or now_version()
    task = resolve_task(config_path, solution_dir)
    child_id = child_id or f"child-{version}"
    ensure_aai_layout(task.definition, campaign_id)

    root = child_root(campaign_id, child_id)
    workspace = root / "workspace"
    parent_snapshot = root / "parent_solution"
    root.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    cfg_src = resolve_project_path(task.config_path)
    sol_src = resolve_project_path(task.solution_dir)
    _copy_file(cfg_src, workspace / "config.toml")
    _copy_file(cfg_src, root / "parent_config.toml")
    _copy_tree(sol_src, workspace / "solution")
    _copy_tree(sol_src, parent_snapshot)

    # Create required placeholders so child workers see the expected contract.
    (root / "ITERATIONS.md").write_text(
        f"# ITERATIONS for {child_id}\n\n- Parent: `{parent_id}`\n- Version: `{version}`\n\n",
        encoding="utf-8",
    )
    write_json(root / "trajectory.json", {"schema": "aai-trajectory.v1", "version": version, "attempts": []})
    write_json(root / "audit.json", {"schema": "aai-audit.v1", "version": version, "findings": []})

    child_meta = {
        "schema": "aai-child-workspace.v1",
        "version": version,
        "campaign_id": campaign_id,
        "child_id": child_id,
        "parent_id": parent_id,
        "task": task,
        "paths": {
            "root": str(root),
            "workspace": str(workspace),
            "workspace_config": str(workspace / "config.toml"),
            "workspace_solution": str(workspace / "solution"),
            "parent_solution": str(parent_snapshot),
            "iterations_md": str(root / "ITERATIONS.md"),
            "trajectory_json": str(root / "trajectory.json"),
            "audit_json": str(root / "audit.json"),
            "diff_patch": str(root / "diff.patch"),
            "result_json": str(root / "result.json"),
        },
    }
    return write_json(root / "child.json", child_meta)


def capture_child_diff(campaign_id: str, child_id: str) -> Path:
    meta_path = child_root(campaign_id, child_id) / "child.json"
    meta = read_json(meta_path)
    paths = meta["paths"]
    return capture_directory_diff(
        paths["parent_solution"],
        paths["workspace_solution"],
        paths["diff_patch"],
        before_label="parent",
        after_label="candidate",
    )


def _metrics_from_benchmark_result(result_path: Path, definition: str) -> Metrics:
    if not result_path.exists():
        return Metrics(status="NO_BENCHMARK_RESULT")
    data = read_json(result_path)
    summary = (data.get("summary") or {}).get(definition) or data.get("summary") or {}
    failed = int(summary.get("failed_workloads") or 0)
    total = int(summary.get("total_workloads") or 0)
    passed = int(summary.get("passed_workloads") or 0)
    status = "PASSED" if total and failed == 0 else "FAILED" if total else "UNKNOWN"
    return Metrics(
        status=status,
        total_workloads=total,
        passed_workloads=passed,
        failed_workloads=failed,
        avg_latency_ms=summary.get("avg_latency_ms"),
        p95_latency_ms=summary.get("p95_latency_ms"),
        median_latency_ms=summary.get("median_latency_ms"),
        min_latency_ms=summary.get("min_latency_ms"),
        max_latency_ms=summary.get("max_latency_ms"),
        avg_speedup_factor=summary.get("avg_speedup_factor"),
    )


def finalize_child_evidence(
    campaign_id: str,
    child_id: str,
    benchmark_result_json: str | Path | None = None,
    retained_log: str | Path | None = None,
    stdout_log: str | Path | None = None,
    stderr_log: str | Path | None = None,
    notes: list[str] | None = None,
) -> Path:
    """Write child `result.json` using the shared EvidenceRecord schema."""
    root = child_root(campaign_id, child_id)
    meta = read_json(root / "child.json")
    task = TaskSpec(**meta["task"])
    diff_path = capture_child_diff(campaign_id, child_id)

    result_path = Path(benchmark_result_json) if benchmark_result_json else root / "benchmark_detailed_results.json"
    metrics = _metrics_from_benchmark_result(result_path, task.definition)
    evidence = EvidenceRecord(
        version=meta["version"],
        run_id=f"{campaign_id}/{child_id}",
        campaign_id=campaign_id,
        child_id=child_id,
        parent_id=meta.get("parent_id"),
        candidate_id=child_id,
        task=task,
        metrics=metrics,
        artifacts=ArtifactRefs(
            result_json=str(result_path) if result_path.exists() else None,
            retained_log=str(retained_log) if retained_log else None,
            diff_patch=str(diff_path),
            stdout_log=str(stdout_log) if stdout_log else None,
            stderr_log=str(stderr_log) if stderr_log else None,
            audit_json=str(root / "audit.json"),
            solution_snapshot=meta["paths"]["workspace_solution"],
            config_snapshot=meta["paths"]["workspace_config"],
        ),
        notes=notes or ["Child evidence finalized from isolated workspace."],
    )
    return write_json(root / "result.json", evidence)


def missing_required_child_files(campaign_id: str, child_id: str) -> list[str]:
    root = child_root(campaign_id, child_id)
    return [name for name in REQUIRED_CHILD_FILES if not (root / name).exists()]
