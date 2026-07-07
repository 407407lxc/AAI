from __future__ import annotations

from pathlib import Path


def repo_root(start: str | Path | None = None) -> Path:
    current = Path(start or ".").resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / "README.md").exists():
            return candidate
    return current


def aai_root(root: str | Path | None = None) -> Path:
    return repo_root(root) / ".aai"


def campaign_root(campaign_id: str, root: str | Path | None = None) -> Path:
    return aai_root(root) / "campaigns" / campaign_id


def workflow_path(campaign_id: str, root: str | Path | None = None) -> Path:
    return campaign_root(campaign_id, root) / "workflow.json"


def resolve_artifact_path(path: str | Path, root: str | Path | None = None) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else repo_root(root) / p
