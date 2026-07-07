from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import PhaseRunResult, write_phase_result


class ManualRuntimeAdapter:
    """Adapter for human-authored or externally produced phase evidence.

    This is intentionally simple: it wraps evidence already created by a human,
    CI job, or external runtime into the standard AAI phase result format.
    """

    runtime_name = "manual"

    def run_phase(self, phase_spec: dict[str, Any]) -> PhaseRunResult:
        campaign_id = str(phase_spec["campaign_id"])
        evidence = {str(k): str(v) for k, v in phase_spec.get("evidence", {}).items()}
        logs = {str(k): str(v) for k, v in phase_spec.get("logs", {}).items()}
        result = PhaseRunResult(
            schema="aai-phase-run-result.v0",
            campaign_id=campaign_id,
            runtime_name=self.runtime_name,
            status=str(phase_spec.get("status", "EVIDENCE_PROVIDED")),
            evidence=evidence,
            logs=logs,
            notes=str(phase_spec.get("notes", "Manual/external evidence was provided.")),
            metadata=dict(phase_spec.get("metadata", {})),
        )
        output_path = Path(phase_spec.get("output_path", ".aai/manual_phase_result.json"))
        write_phase_result(output_path, result)
        return result


def run_from_file(path: str | Path) -> Path:
    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    result = ManualRuntimeAdapter().run_phase(spec)
    output_path = Path(spec.get("output_path", ".aai/manual_phase_result.json"))
    if not output_path.exists():
        write_phase_result(output_path, result)
    return output_path
