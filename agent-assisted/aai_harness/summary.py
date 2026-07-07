from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import campaign_root
from .schemas import now_version, read_json, write_json


@dataclass(slots=True)
class CampaignRollup:
    schema: str = "aai-campaign-summary.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    metric: str = "avg_latency_ms"
    definition: str | None = None
    total_children: int = 0
    total_round_reports: int = 0
    gate_passed: int = 0
    archived_variants: int = 0
    archived_failed: int = 0
    archived_baselines: int = 0
    missing_round_reports: int = 0
    best_child_id: str | None = None
    best_metric_value: float | None = None
    status_counts: dict[str, int] = field(default_factory=dict)
    mode_counts: dict[str, int] = field(default_factory=dict)
    archive_kind_counts: dict[str, int] = field(default_factory=dict)
    gate_failure_codes: dict[str, int] = field(default_factory=dict)
    children: list[dict[str, Any]] = field(default_factory=list)
    recommended_next_steps: list[str] = field(default_factory=list)


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    try:
        return read_json(path)
    except Exception:
        return None


def _metric_from_evidence(evidence_path: str | None, metric: str) -> tuple[float | None, str | None]:
    if not evidence_path:
        return None, None
    evidence = _safe_read_json(Path(evidence_path))
    if not evidence:
        return None, None
    task = evidence.get("task") or {}
    metrics = evidence.get("metrics") or {}
    value = metrics.get(metric)
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return value, task.get("definition")


def _gate_codes(gate_path: str | None) -> list[str]:
    if not gate_path:
        return []
    gate = _safe_read_json(Path(gate_path))
    if not gate:
        return []
    codes: list[str] = []
    for finding in gate.get("findings") or []:
        if finding.get("severity") == "error":
            codes.append(str(finding.get("code") or "unknown_error"))
    return codes


def _render_markdown(summary: CampaignRollup) -> str:
    lines = [
        f"# AAI Campaign Summary: {summary.campaign_id}",
        "",
        f"- Version: `{summary.version}`",
        f"- Definition: `{summary.definition or 'unknown'}`",
        f"- Metric: `{summary.metric}`",
        f"- Children: {summary.total_children}",
        f"- Round reports: {summary.total_round_reports}",
        f"- Gate passed: {summary.gate_passed}",
        f"- Archived variants: {summary.archived_variants}",
        f"- Archived failed: {summary.archived_failed}",
        f"- Archived baselines: {summary.archived_baselines}",
        f"- Best child: `{summary.best_child_id or 'none'}`",
        f"- Best metric value: `{summary.best_metric_value if summary.best_metric_value is not None else 'none'}`",
        "",
        "## Status counts",
        "",
    ]
    if summary.status_counts:
        lines.extend(f"- `{key}`: {value}" for key, value in sorted(summary.status_counts.items()))
    else:
        lines.append("- none")

    lines.extend(["", "## Gate failure codes", ""])
    if summary.gate_failure_codes:
        lines.extend(f"- `{key}`: {value}" for key, value in sorted(summary.gate_failure_codes.items()))
    else:
        lines.append("- none")

    lines.extend([
        "",
        "## Children",
        "",
        "| child | parent | mode | status | final archive | gate | metric |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    for child in summary.children:
        metric_value = child.get("metric_value")
        lines.append(
            "| {child_id} | {parent_id} | {mode} | {status} | {final_kind} | {gate} | {metric} |".format(
                child_id=f"`{child.get('child_id')}`",
                parent_id=f"`{child.get('parent_id')}`",
                mode=f"`{child.get('mode')}`",
                status=f"`{child.get('status')}`",
                final_kind=f"`{child.get('final_archive_kind')}`",
                gate="pass" if child.get("gate_passed") else "fail",
                metric=metric_value if metric_value is not None else "none",
            )
        )

    lines.extend(["", "## Recommended next steps", ""])
    lines.extend(f"- {item}" for item in summary.recommended_next_steps)
    return "\n".join(lines) + "\n"


def summarize_campaign(campaign_id: str, metric: str = "avg_latency_ms") -> tuple[Path, Path]:
    root = campaign_root(campaign_id)
    children_root = root / "children"
    summary = CampaignRollup(campaign_id=campaign_id, metric=metric)

    child_dirs = sorted([path for path in children_root.glob("*") if path.is_dir()]) if children_root.exists() else []
    summary.total_children = len(child_dirs)

    status_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    archive_kind_counts: Counter[str] = Counter()
    gate_failure_codes: Counter[str] = Counter()
    best_value: float | None = None
    best_child: str | None = None

    for child_dir in child_dirs:
        report_path = child_dir / "round_report.json"
        if not report_path.exists():
            summary.missing_round_reports += 1
            summary.children.append({
                "child_id": child_dir.name,
                "status": "MISSING_ROUND_REPORT",
                "round_report": str(report_path),
            })
            status_counts["MISSING_ROUND_REPORT"] += 1
            continue

        report = read_json(report_path)
        summary.total_round_reports += 1
        child_id = str(report.get("child_id") or child_dir.name)
        final_kind = str(report.get("final_archive_kind") or "unknown")
        status = str(report.get("status") or "UNKNOWN")
        mode = str(report.get("mode") or "unknown")
        gate_passed = bool(report.get("gate_passed"))
        metric_value, definition = _metric_from_evidence(report.get("evidence_json"), metric)
        if definition and not summary.definition:
            summary.definition = definition

        if gate_passed:
            summary.gate_passed += 1
        if final_kind == "variant":
            summary.archived_variants += 1
        elif final_kind == "failed":
            summary.archived_failed += 1
        elif final_kind == "baseline":
            summary.archived_baselines += 1

        status_counts[status] += 1
        mode_counts[mode] += 1
        archive_kind_counts[final_kind] += 1
        for code in _gate_codes(report.get("gate_json")):
            gate_failure_codes[code] += 1

        if gate_passed and final_kind == "variant" and metric_value is not None:
            if best_value is None or metric_value < best_value:
                best_value = metric_value
                best_child = child_id

        summary.children.append({
            "child_id": child_id,
            "parent_id": report.get("parent_id"),
            "mode": mode,
            "status": status,
            "requested_archive_kind": report.get("requested_archive_kind"),
            "final_archive_kind": final_kind,
            "gate_passed": gate_passed,
            "metric": metric,
            "metric_value": metric_value,
            "round_report": str(report_path),
            "evidence_json": report.get("evidence_json"),
            "gate_json": report.get("gate_json"),
            "archive_manifest": report.get("archive_manifest"),
            "notes": report.get("notes") or [],
        })

    summary.status_counts = dict(status_counts)
    summary.mode_counts = dict(mode_counts)
    summary.archive_kind_counts = dict(archive_kind_counts)
    summary.gate_failure_codes = dict(gate_failure_codes)
    summary.best_child_id = best_child
    summary.best_metric_value = best_value

    if summary.total_children == 0:
        summary.recommended_next_steps.append("Run at least one child round with `run-child-round`.")
    elif summary.archived_variants == 0:
        summary.recommended_next_steps.append("Run a promotion-quality child round, usually with `--mode modal-full`.")
    else:
        summary.recommended_next_steps.append("Use `select-parent` or the best child from this summary to seed the next round.")
    if summary.gate_failure_codes:
        summary.recommended_next_steps.append("Review repeated gate failure codes and convert recurring issues into TRAPS or Mode 3 proposals.")
    if summary.missing_round_reports:
        summary.recommended_next_steps.append("Finalize or rerun children that are missing `round_report.json`.")

    json_path = write_json(root / "campaign_summary.json", summary)
    md_path = root / "campaign_summary.md"
    md_path.write_text(_render_markdown(summary), encoding="utf-8")
    return json_path, md_path
