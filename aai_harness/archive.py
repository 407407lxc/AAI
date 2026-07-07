from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .artifacts import build_manifest, write_manifest
from .paths import aai_root, resolve_artifact_path
from .workflow import utc_now


@dataclass(frozen=True)
class ArchiveRecord:
    schema: str
    campaign_id: str
    archive_type: str
    created_at: str
    root: str
    artifacts: dict[str, str]
    copied_artifacts: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def archive_base(campaign_id: str, root: str | Path | None = None) -> Path:
    return aai_root(root) / "archive" / campaign_id


def _safe_name(name: str) -> str:
    return name.replace("/", "_").replace(" ", "_").replace(":", "_")


def archive_run(
    campaign_id: str,
    archive_type: str,
    artifacts: dict[str, str],
    root: str | Path | None = None,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
    copy_artifacts: bool = True,
) -> Path:
    version = utc_now().replace(":", "").replace("+", "Z")
    out = archive_base(campaign_id, root) / _safe_name(archive_type) / version
    out.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(campaign_id, artifacts, root=root)
    write_manifest(out / "artifact_manifest.json", manifest)

    copied: dict[str, str] = {}
    if copy_artifacts:
        copied_root = out / "artifacts"
        copied_root.mkdir(parents=True, exist_ok=True)
        for name, path in artifacts.items():
            source = resolve_artifact_path(path, root)
            if not source.exists():
                continue
            target = copied_root / _safe_name(name)
            if source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            copied[name] = str(target)

    record = ArchiveRecord(
        schema="aai-archive-record.v0",
        campaign_id=campaign_id,
        archive_type=archive_type,
        created_at=version,
        root=str(out),
        artifacts=artifacts,
        copied_artifacts=copied,
        notes=notes,
        metadata=metadata or {},
    )
    record_path = out / "manifest.json"
    record_path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    append_ledger(campaign_id, archive_type, record_path, root=root, notes=notes)
    return record_path


def append_ledger(
    campaign_id: str,
    archive_type: str,
    manifest_path: str | Path,
    root: str | Path | None = None,
    notes: str = "",
) -> Path:
    ledger = archive_base(campaign_id, root) / "harness-ledger.md"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {utc_now()} {archive_type}\n")
        fh.write(f"- manifest: `{manifest_path}`\n")
        if notes:
            fh.write(f"- notes: {notes}\n")
    return ledger
