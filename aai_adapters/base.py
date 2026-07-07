from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class PhaseRunResult:
    schema: str
    campaign_id: str
    runtime_name: str
    status: str
    evidence: dict[str, str]
    logs: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_phase_result(path: str | Path, result: PhaseRunResult) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return out


class RuntimeAdapter(Protocol):
    runtime_name: str

    def run_phase(self, phase_spec: dict[str, Any]) -> PhaseRunResult:
        """Run a phase-local runtime and return an evidence bundle.

        Adapters must not advance the global AAI workflow state. They only produce
        evidence for the outer AAI control plane to validate and consume.
        """
        ...
