from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .schemas import GateFinding, GateResult, VERSION_SCHEMA, read_json, write_json

PROTECTED_PATTERNS = [
    "reference/",
    "flashinfer-trace/",
    "mlsys26-contest/",
    "benchmark_detailed_results.json",
    "retained_run.log",
    "scripts/run_local.py",
    "scripts/run_modal_single.py",
    "scripts/run_modal_multiple_gpus.py",
    "scripts/pack_solution.py",
]

SUSPICIOUS_PATTERNS = [
    re.compile(r"hidden[_-]?eval", re.I),
    re.compile(r"leaderboard", re.I),
    re.compile(r"workload_uuid\s*==", re.I),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I),
]


def _add(findings: list[GateFinding], severity: str, code: str, message: str, path: str | None = None) -> None:
    findings.append(GateFinding(severity=severity, code=code, message=message, path=path))  # type: ignore[arg-type]


def _iter_diff_paths(diff_text: str) -> Iterable[str]:
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                yield parts[2].removeprefix("a/")
                yield parts[3].removeprefix("b/")


def gate_evidence(evidence_path: str | Path, diff_path: str | Path | None = None) -> GateResult:
    findings: list[GateFinding] = []
    try:
        evidence = read_json(evidence_path)
    except Exception as exc:
        _add(findings, "error", "evidence_unreadable", f"cannot read evidence json: {exc}", str(evidence_path))
        return GateResult(passed=False, findings=findings)

    if evidence.get("schema") != VERSION_SCHEMA:
        _add(findings, "error", "schema_mismatch", f"expected {VERSION_SCHEMA}, got {evidence.get('schema')}", str(evidence_path))

    metrics = evidence.get("metrics") or {}
    status = str(metrics.get("status", "UNKNOWN"))
    failed = int(metrics.get("failed_workloads") or 0)
    if failed > 0 or status.endswith("FAILED") or status in {"FAILED", "ERROR", "TIMEOUT", "PARSE_ERROR"}:
        _add(findings, "error", "benchmark_failed", f"status={status}, failed_workloads={failed}")

    if diff_path:
        diff_text = Path(diff_path).read_text(encoding="utf-8", errors="replace")
        for changed in sorted(set(_iter_diff_paths(diff_text))):
            if any(pattern in changed for pattern in PROTECTED_PATTERNS):
                _add(findings, "error", "protected_path_modified", "candidate touched a protected evaluator/baseline path", changed)
            elif not (changed.startswith("solution/") or "/solution/" in changed):
                _add(findings, "warning", "outside_solution_scope", "candidate changed a path outside solution/", changed)
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(diff_text):
                _add(findings, "error", "suspicious_diff_pattern", f"matched pattern {pattern.pattern}", str(diff_path))

    passed = not any(f.severity == "error" for f in findings)
    if passed:
        _add(findings, "info", "gate_passed", "evidence passed default AAI archive gate")
    return GateResult(passed=passed, findings=findings)


def write_gate_result(output_path: str | Path, result: GateResult) -> Path:
    return write_json(output_path, result)
