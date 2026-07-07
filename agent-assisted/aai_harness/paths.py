from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent          # agent-assisted/
REPO_ROOT = PROJECT_ROOT.parent
AAI_ROOT = PROJECT_ROOT / ".aai"


def resolve_project_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_toml(path: str | Path) -> dict[str, Any]:
    with open(resolve_project_path(path), "rb") as f:
        return tomllib.load(f)


def definition_from_config(config_path: str | Path) -> str:
    return read_toml(config_path)["solution"]["definition"]


def language_from_config(config_path: str | Path) -> str:
    return read_toml(config_path)["build"]["language"]


def default_solution_dir(config_path: str | Path) -> Path:
    cfg_path = resolve_project_path(config_path)
    return cfg_path.parent / "solution" / language_from_config(cfg_path)


def campaign_root(campaign_id: str) -> Path:
    return AAI_ROOT / "campaigns" / campaign_id


def archive_root(definition: str) -> Path:
    return AAI_ROOT / "archive" / definition


def baseline_root(definition: str) -> Path:
    return archive_root(definition) / "baseline"


def variants_root(definition: str) -> Path:
    return archive_root(definition) / "variants"


def failed_root(definition: str) -> Path:
    return archive_root(definition) / "failed"


def ensure_aai_layout(definition: str | None = None, campaign_id: str | None = None) -> list[Path]:
    roots = [AAI_ROOT]
    if definition:
        roots.extend([
            baseline_root(definition),
            variants_root(definition),
            failed_root(definition),
            archive_root(definition) / "traps",
        ])
    if campaign_id:
        roots.extend([
            campaign_root(campaign_id) / "children",
            campaign_root(campaign_id) / "proposals",
            campaign_root(campaign_id) / "logs",
        ])
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
    return roots
