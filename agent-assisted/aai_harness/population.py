from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import archive_root, campaign_root
from .schemas import now_version, read_json, write_json


@dataclass(slots=True)
class PopulationMember:
    id: str
    child_id: str
    campaign_id: str
    parent_id: str
    archive_kind: str
    status: str
    gate_passed: bool
    metric: str
    metric_value: float | None
    evidence_json: str | None = None
    archive_manifest: str | None = None
    created_at: str = field(default_factory=now_version)


@dataclass(slots=True)
class PopulationSnapshot:
    schema: str = "aai-population.v1"
    version: str = field(default_factory=now_version)
    definition: str = ""
    metric: str = "avg_latency_ms"
    members: list[PopulationMember] = field(default_factory=list)
    best_member_id: str | None = None
    checkpoints: list[str] = field(default_factory=list)


def population_path(definition: str) -> Path:
    return archive_root(definition) / "population" / "population.json"


def checkpoint_dir(definition: str, version: str | None = None) -> Path:
    version = version or now_version()
    return archive_root(definition) / "population" / "checkpoints" / f"checkpoint-{version}"


def _load_population(definition: str, metric: str) -> PopulationSnapshot:
    path = population_path(definition)
    if not path.exists():
        return PopulationSnapshot(definition=definition, metric=metric)
    data = read_json(path)
    members = [PopulationMember(**item) for item in data.get("members", [])]
    keep = {name for name in PopulationSnapshot.__dataclass_fields__}
    payload = {k: v for k, v in data.items() if k in keep and k != "members"}
    if not payload.get("definition"):
        payload["definition"] = definition
    if not payload.get("metric"):
        payload["metric"] = metric
    return PopulationSnapshot(**payload, members=members)


def _metric_from_evidence(evidence_path: str | None, metric: str) -> float | None:
    if not evidence_path:
        return None
    path = Path(evidence_path)
    if not path.exists():
        return None
    evidence = read_json(path)
    metrics = evidence.get("metrics") or {}
    value = metrics.get(metric)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _best_member_id(members: list[PopulationMember]) -> str | None:
    usable = [m for m in members if m.gate_passed and m.archive_kind == "variant" and m.metric_value is not None]
    if not usable:
        return None
    return min(usable, key=lambda member: member.metric_value or float("inf")).id


def admit_round_report(
    campaign_id: str,
    child_id: str,
    definition: str,
    metric: str = "avg_latency_ms",
) -> Path:
    """Admit a child round into the AAI population database.

    This is the LoongFlow-inspired population/checkpoint layer. It records all
    archived variants and failures, while only gated variants are eligible for
    best-member selection.
    """
    report_path = campaign_root(campaign_id) / "children" / child_id / "round_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"round report not found: {report_path}")
    report = read_json(report_path)
    population = _load_population(definition, metric)
    member_id = f"{campaign_id}:{child_id}:{report.get('final_archive_kind', 'unknown')}"
    existing = [member for member in population.members if member.id != member_id]
    metric_value = _metric_from_evidence(report.get("evidence_json"), metric)
    member = PopulationMember(
        id=member_id,
        child_id=child_id,
        campaign_id=campaign_id,
        parent_id=str(report.get("parent_id") or "baseline"),
        archive_kind=str(report.get("final_archive_kind") or "unknown"),
        status=str(report.get("status") or "UNKNOWN"),
        gate_passed=bool(report.get("gate_passed")),
        metric=metric,
        metric_value=metric_value,
        evidence_json=report.get("evidence_json"),
        archive_manifest=report.get("archive_manifest"),
    )
    population.members = existing + [member]
    population.version = now_version()
    population.best_member_id = _best_member_id(population.members)
    pop_path = write_json(population_path(definition), population)

    ckpt = checkpoint_dir(definition, population.version)
    ckpt.mkdir(parents=True, exist_ok=True)
    write_json(ckpt / "population.json", population)
    write_json(ckpt / "admitted_member.json", member)
    population.checkpoints.append(str(ckpt))
    write_json(pop_path, population)
    return pop_path


def population_status(definition: str, metric: str = "avg_latency_ms") -> dict[str, Any]:
    population = _load_population(definition, metric)
    return {
        "definition": definition,
        "metric": population.metric,
        "member_count": len(population.members),
        "best_member_id": population.best_member_id,
        "members": [member.__dict__ for member in population.members],
        "checkpoints": population.checkpoints,
    }
