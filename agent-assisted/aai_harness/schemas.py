from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

VERSION_SCHEMA = "aai-harness.v1"
DEFAULT_TIMEZONE = "Asia/Tokyo"


def now_version(timezone: str = DEFAULT_TIMEZONE) -> str:
    """Return a filesystem-safe timestamp version, e.g. 20260707T160734+0900."""
    return datetime.now(ZoneInfo(timezone)).strftime("%Y%m%dT%H%M%S%z")


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if is_dataclass(payload):
        payload = asdict(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


@dataclass(slots=True)
class TaskSpec:
    """Resolved requirements for one kernel optimization target."""

    definition: str
    config_path: str
    solution_dir: str
    runtime: Literal["local", "modal", "official"] = "modal"
    hardware: str = "B200"
    primary_metric: str = "avg_latency_ms"
    quality_gates: list[str] = field(default_factory=lambda: [
        "correctness_passed",
        "no_eval_leakage",
        "no_hardcoded_answers",
        "no_baseline_mutation",
        "schema_valid",
    ])
    credentials_policy: str = "never archive secrets; pass credentials only through environment variables"


@dataclass(slots=True)
class Metrics:
    status: str = "UNKNOWN"
    total_workloads: int = 0
    passed_workloads: int = 0
    failed_workloads: int = 0
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    median_latency_ms: float | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    avg_speedup_factor: float | None = None


@dataclass(slots=True)
class ArtifactRefs:
    result_json: str | None = None
    retained_log: str | None = None
    diff_patch: str | None = None
    stdout_log: str | None = None
    stderr_log: str | None = None
    audit_json: str | None = None
    solution_snapshot: str | None = None
    config_snapshot: str | None = None


@dataclass(slots=True)
class GateFinding:
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    path: str | None = None


@dataclass(slots=True)
class GateResult:
    schema: str = VERSION_SCHEMA
    version: str = field(default_factory=now_version)
    passed: bool = False
    findings: list[GateFinding] = field(default_factory=list)


@dataclass(slots=True)
class EvidenceRecord:
    schema: str = VERSION_SCHEMA
    version: str = field(default_factory=now_version)
    run_id: str = ""
    campaign_id: str | None = None
    child_id: str | None = None
    parent_id: str | None = None
    candidate_id: str | None = None
    task: TaskSpec | None = None
    metrics: Metrics = field(default_factory=Metrics)
    artifacts: ArtifactRefs = field(default_factory=ArtifactRefs)
    gate: GateResult | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProposalReview:
    schema: str = VERSION_SCHEMA
    version: str = field(default_factory=now_version)
    proposal_path: str = ""
    accepted: bool = False
    reasons: list[str] = field(default_factory=list)
    required_followups: list[str] = field(default_factory=list)
