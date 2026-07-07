from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import resolve_artifact_path


@dataclass(frozen=True)
class ArtifactManifestEntry:
    name: str
    path: str
    kind: str
    exists: bool
    sha256: str | None = None
    size_bytes: int | None = None
    description: str = ""


@dataclass(frozen=True)
class ArtifactManifest:
    schema: str
    campaign_id: str
    entries: list[ArtifactManifestEntry] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["entries"] = [asdict(entry) for entry in self.entries]
        return payload


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_path(path: Path) -> str:
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "missing"


def inspect_artifact(
    name: str,
    path: str | Path,
    root: str | Path | None = None,
    description: str = "",
) -> ArtifactManifestEntry:
    resolved = resolve_artifact_path(path, root)
    exists = resolved.exists()
    kind = classify_path(resolved)
    sha = file_sha256(resolved) if resolved.is_file() else None
    size = resolved.stat().st_size if resolved.is_file() else None
    return ArtifactManifestEntry(
        name=name,
        path=str(resolved),
        kind=kind,
        exists=exists,
        sha256=sha,
        size_bytes=size,
        description=description,
    )


def build_manifest(
    campaign_id: str,
    artifacts: dict[str, str],
    root: str | Path | None = None,
    schema: str = "aai-artifact-manifest.v0",
) -> ArtifactManifest:
    entries = [inspect_artifact(name, path, root=root) for name, path in artifacts.items()]
    findings = []
    for entry in entries:
        if not entry.exists:
            findings.append({"level": "error", "code": "missing_artifact", "name": entry.name, "path": entry.path})
    return ArtifactManifest(schema=schema, campaign_id=campaign_id, entries=entries, findings=findings)


def write_manifest(path: str | Path, manifest: ArtifactManifest) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return out


def protected_path_findings(
    changed_paths: list[str],
    protected_prefixes: list[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    normalized_prefixes = [prefix.strip().rstrip("/") for prefix in protected_prefixes if prefix.strip()]
    for changed in changed_paths:
        clean = changed.strip().lstrip("./")
        for prefix in normalized_prefixes:
            if clean == prefix or clean.startswith(prefix + "/"):
                findings.append({
                    "level": "error",
                    "code": "protected_path_modified",
                    "path": clean,
                    "protected_prefix": prefix,
                    "message": f"Runtime modified protected path: {clean}",
                })
    return findings
