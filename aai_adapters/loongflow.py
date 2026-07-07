from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import PhaseRunResult, write_phase_result


@dataclass(frozen=True)
class LoongFlowPhaseSpec:
    campaign_id: str
    runtime_root: str
    command: list[str]
    output_path: str
    trace_path: str | None = None
    env_required: list[str] = field(default_factory=list)
    timeout_s: int = 7200


class LoongFlowPhaseAdapter:
    """Run LoongFlow as an inner phase runtime.

    LoongFlow may plan, execute, evaluate, summarize, and checkpoint inside the
    phase. This adapter only records its result as evidence. It does not advance
    the global AAI workflow and does not write archive or memory directly.
    """

    runtime_name = "loongflow"

    def run_phase(self, phase_spec: dict[str, Any]) -> PhaseRunResult:
        spec = LoongFlowPhaseSpec(
            campaign_id=str(phase_spec["campaign_id"]),
            runtime_root=str(phase_spec["runtime_root"]),
            command=[str(x) for x in phase_spec["command"]],
            output_path=str(phase_spec.get("output_path", ".aai/loongflow_phase_result.json")),
            trace_path=phase_spec.get("trace_path"),
            env_required=[str(x) for x in phase_spec.get("env_required", [])],
            timeout_s=int(phase_spec.get("timeout_s", 7200)),
        )
        env = os.environ.copy()
        missing_env = [name for name in spec.env_required if not env.get(name)]
        logs: dict[str, str] = {}
        metadata: dict[str, Any] = {"command": spec.command, "runtime_root": spec.runtime_root, "missing_env": missing_env}

        if missing_env:
            status = "MISSING_ENV"
        else:
            root = Path(spec.runtime_root).resolve()
            root.mkdir(parents=True, exist_ok=True)
            output_path = Path(spec.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            stdout = output_path.with_suffix(".stdout.log")
            stderr = output_path.with_suffix(".stderr.log")
            proc = subprocess.run(
                spec.command,
                cwd=str(root),
                env=env,
                text=True,
                capture_output=True,
                timeout=spec.timeout_s,
                check=False,
            )
            stdout.write_text(proc.stdout or "", encoding="utf-8")
            stderr.write_text(proc.stderr or "", encoding="utf-8")
            logs = {"stdout": str(stdout), "stderr": str(stderr)}
            metadata["returncode"] = proc.returncode
            status = "PASSED" if proc.returncode == 0 else "FAILED"

        evidence: dict[str, str] = {}
        if spec.trace_path:
            evidence["trace"] = spec.trace_path
        result = PhaseRunResult(
            schema="aai-phase-run-result.v0",
            campaign_id=spec.campaign_id,
            runtime_name=self.runtime_name,
            status=status,
            evidence=evidence,
            logs=logs,
            notes="LoongFlow was run as a phase-local runtime.",
            metadata=metadata,
        )
        return write_phase_result(spec.output_path, result) and result


def run_from_file(path: str | Path) -> Path:
    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    adapter = LoongFlowPhaseAdapter()
    result = adapter.run_phase(spec)
    output_path = Path(spec.get("output_path", ".aai/loongflow_phase_result.json"))
    if not output_path.exists():
        write_phase_result(output_path, result)
    return output_path
