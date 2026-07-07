from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import aai_root, campaign_root
from .workflow import utc_now


@dataclass(frozen=True)
class MemoryUpdate:
    schema: str
    campaign_id: str
    created_at: str
    outcome: str
    summary: str
    lessons: list[str] = field(default_factory=list)
    traps: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def memory_root(root: str | Path | None = None) -> Path:
    return aai_root(root) / "memory"


def write_memory_update(
    campaign_id: str,
    outcome: str,
    summary: str,
    lessons: list[str] | None = None,
    traps: list[str] | None = None,
    next_actions: list[str] | None = None,
    evidence: dict[str, str] | None = None,
    root: str | Path | None = None,
) -> Path:
    update = MemoryUpdate(
        schema="aai-memory-update.v0",
        campaign_id=campaign_id,
        created_at=utc_now(),
        outcome=outcome,
        summary=summary,
        lessons=lessons or [],
        traps=traps or [],
        next_actions=next_actions or [],
        evidence=evidence or {},
    )
    out = campaign_root(campaign_id, root) / "memory" / "memory_update.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(update.to_dict(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    append_global_memory(update, root=root)
    return out


def append_global_memory(update: MemoryUpdate, root: str | Path | None = None) -> None:
    root_path = memory_root(root)
    root_path.mkdir(parents=True, exist_ok=True)

    ledger = root_path / "harness-ledger.md"
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {update.created_at} campaign={update.campaign_id} outcome={update.outcome}\n")
        fh.write(f"- summary: {update.summary}\n")
        for action in update.next_actions:
            fh.write(f"- next: {action}\n")

    if update.traps:
        traps_file = root_path / "TRAPS.md"
        with traps_file.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {update.created_at} campaign={update.campaign_id}\n")
            for trap in update.traps:
                fh.write(f"- {trap}\n")

    if update.lessons:
        lessons_file = root_path / "LESSONS.md"
        with lessons_file.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {update.created_at} campaign={update.campaign_id}\n")
            for lesson in update.lessons:
                fh.write(f"- {lesson}\n")
