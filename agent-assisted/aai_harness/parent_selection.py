from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import archive_root, baseline_root, variants_root
from .schemas import now_version, read_json, write_json


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    try:
        return read_json(path) if path.exists() else None
    except Exception:
        return None


def _candidate_from_evidence(path: Path, kind: str) -> dict[str, Any] | None:
    evidence = _load_json_if_exists(path)
    if not evidence:
        return None
    metrics = evidence.get("metrics") or {}
    task = evidence.get("task") or {}
    return {
        "kind": kind,
        "id": evidence.get("candidate_id") or path.parent.name,
        "version": evidence.get("version") or path.parent.name,
        "path": str(path.parent),
        "evidence_json": str(path),
        "definition": task.get("definition"),
        "status": metrics.get("status"),
        "failed_workloads": metrics.get("failed_workloads"),
        "avg_latency_ms": metrics.get("avg_latency_ms"),
        "p95_latency_ms": metrics.get("p95_latency_ms"),
        "median_latency_ms": metrics.get("median_latency_ms"),
        "avg_speedup_factor": metrics.get("avg_speedup_factor"),
    }


def list_parent_candidates(definition: str) -> list[dict[str, Any]]:
    """Return baseline and archived variant candidates for a definition."""
    candidates: list[dict[str, Any]] = []
    for root, kind in [(baseline_root(definition), "baseline"), (variants_root(definition), "variant")]:
        if not root.exists():
            continue
        for evidence_path in sorted(root.glob("*/evidence.json")):
            candidate = _candidate_from_evidence(evidence_path, kind)
            if candidate:
                candidates.append(candidate)
    return candidates


def select_parent(
    definition: str,
    metric: str = "avg_latency_ms",
    allow_failed: bool = False,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Select the best parent by lowest latency metric, falling back to latest baseline.

    Variants are preferred when they have a usable metric and no failed workloads.
    If no usable variant exists, the newest baseline evidence is returned.
    """
    candidates = list_parent_candidates(definition)
    usable: list[dict[str, Any]] = []
    for cand in candidates:
        metric_value = cand.get(metric)
        if metric_value is None:
            continue
        if not allow_failed and int(cand.get("failed_workloads") or 0) > 0:
            continue
        usable.append(cand)

    selected: dict[str, Any] | None = None
    if usable:
        selected = sorted(usable, key=lambda c: (float(c[metric]), c.get("kind") != "variant", c.get("version") or ""))[0]
    else:
        baselines = [c for c in candidates if c.get("kind") == "baseline"]
        if baselines:
            selected = sorted(baselines, key=lambda c: c.get("version") or "", reverse=True)[0]

    result = {
        "schema": "aai-parent-selection.v1",
        "version": now_version(),
        "definition": definition,
        "metric": metric,
        "allow_failed": allow_failed,
        "selected": selected,
        "candidate_count": len(candidates),
        "usable_count": len(usable),
    }
    if output_path:
        write_json(output_path, result)
    else:
        out = archive_root(definition) / "selected-parent.json"
        write_json(out, result)
    return result
