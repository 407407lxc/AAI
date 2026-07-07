from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .archive import update_ledger, update_traps
from .paths import archive_root, campaign_root
from .schemas import now_version, read_json, write_json
from .summary import summarize_campaign


@dataclass(slots=True)
class CampaignMemoryUpdate:
    schema: str = "aai-campaign-memory-update.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    definition: str = ""
    summary_json: str = ""
    summary_md: str = ""
    ledger_path: str = ""
    traps_path: str | None = None
    ledger_entries: list[str] = field(default_factory=list)
    trap_entries: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_or_create_summary(campaign_id: str, metric: str) -> tuple[dict[str, Any], Path, Path]:
    root = campaign_root(campaign_id)
    summary_json = root / "campaign_summary.json"
    summary_md = root / "campaign_summary.md"
    if not summary_json.exists() or not summary_md.exists():
        summary_json, summary_md = summarize_campaign(campaign_id, metric=metric)
    return read_json(summary_json), summary_json, summary_md


def _infer_definition(summary: dict[str, Any], explicit_definition: str | None) -> str | None:
    if explicit_definition:
        return explicit_definition
    definition = summary.get("definition")
    if definition:
        return str(definition)
    for child in summary.get("children") or []:
        evidence_path = child.get("evidence_json")
        if not evidence_path:
            continue
        try:
            evidence = read_json(evidence_path)
        except Exception:
            continue
        task = evidence.get("task") or {}
        if task.get("definition"):
            return str(task["definition"])
    return None


def _compact_child_list(children: list[dict[str, Any]], limit: int = 8) -> str:
    items = []
    for child in children[:limit]:
        items.append(
            f"{child.get('child_id')}[{child.get('final_archive_kind')}/{child.get('status')}/gate={'pass' if child.get('gate_passed') else 'fail'}]"
        )
    remaining = max(0, len(children) - limit)
    if remaining:
        items.append(f"+{remaining} more")
    return ", ".join(items) if items else "none"


def _trap_entries_from_summary(summary: dict[str, Any], min_failure_count: int) -> list[str]:
    entries: list[str] = []
    failure_codes = summary.get("gate_failure_codes") or {}
    for code, count in sorted(failure_codes.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))):
        if int(count) >= min_failure_count:
            entries.append(f"`{code}` occurred {count} time(s) in campaign `{summary.get('campaign_id')}`; inspect gate.json before repeating this search direction.")

    failed_children = [child for child in summary.get("children") or [] if child.get("final_archive_kind") == "failed"]
    status_counts = Counter(str(child.get("status") or "UNKNOWN") for child in failed_children)
    for status, count in sorted(status_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count >= min_failure_count:
            entries.append(f"Failed child status `{status}` occurred {count} time(s) in campaign `{summary.get('campaign_id')}`; check logs and avoid repeating identical prompts.")
    return entries


def update_campaign_memory(
    campaign_id: str,
    definition: str | None = None,
    metric: str = "avg_latency_ms",
    min_failure_count: int = 1,
    write_traps: bool = True,
) -> Path:
    """Append campaign summary findings into the long-term archive memory.

    This is the Master Campaign memory update step. It reads or creates the
    campaign summary, appends a compact ledger entry, and optionally turns
    repeated gate failures / failed statuses into TRAPS entries.
    """
    summary, summary_json, summary_md = _load_or_create_summary(campaign_id, metric=metric)
    resolved_definition = _infer_definition(summary, definition)
    root = campaign_root(campaign_id)

    update = CampaignMemoryUpdate(
        campaign_id=campaign_id,
        definition=resolved_definition or "unknown",
        summary_json=str(summary_json),
        summary_md=str(summary_md),
    )

    if not resolved_definition:
        update.warnings.append("Cannot update archive memory without a definition; pass --definition or run a child round with evidence first.")
        return write_json(root / "memory_update.json", update)

    children = summary.get("children") or []
    ledger_entry = (
        f"- `{update.version}` campaign `{campaign_id}` summary: "
        f"children={summary.get('total_children', 0)}, "
        f"round_reports={summary.get('total_round_reports', 0)}, "
        f"gate_passed={summary.get('gate_passed', 0)}, "
        f"variants={summary.get('archived_variants', 0)}, "
        f"failed={summary.get('archived_failed', 0)}, "
        f"best_child=`{summary.get('best_child_id') or 'none'}`, "
        f"best_{metric}=`{summary.get('best_metric_value') if summary.get('best_metric_value') is not None else 'none'}`, "
        f"children={_compact_child_list(children)}."
    )
    ledger_path = update_ledger(resolved_definition, ledger_entry)
    update.ledger_path = str(ledger_path)
    update.ledger_entries.append(ledger_entry)

    if summary.get("recommended_next_steps"):
        next_steps = "; ".join(str(item) for item in summary["recommended_next_steps"])
        next_entry = f"- `{update.version}` campaign `{campaign_id}` recommended next steps: {next_steps}"
        update_ledger(resolved_definition, next_entry)
        update.ledger_entries.append(next_entry)

    if write_traps:
        trap_entries = _trap_entries_from_summary(summary, min_failure_count=min_failure_count)
        for entry in trap_entries:
            trap_path = update_traps(resolved_definition, entry)
            update.traps_path = str(trap_path)
            update.trap_entries.append(entry)

    if not update.trap_entries and write_traps:
        update.warnings.append("No trap entries met the configured threshold.")

    return write_json(root / "memory_update.json", update)
