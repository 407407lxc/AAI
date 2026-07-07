from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .archive import archive_evidence
from .child_eval import EvalMode, run_child_evaluation
from .gates import gate_evidence
from .paths import resolve_project_path
from .schemas import GateResult, now_version, write_json
from .workspace import child_root, prepare_child_workspace

ArchiveKind = Literal["baseline", "variant", "failed"]


@dataclass(slots=True)
class ChildRoundReport:
    schema: str = "aai-child-round.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    child_id: str = ""
    parent_id: str = "baseline"
    mode: str = "pack"
    requested_archive_kind: str = "variant"
    final_archive_kind: str = "failed"
    status: str = "UNKNOWN"
    prepared_child_json: str | None = None
    child_eval_json: str | None = None
    evidence_json: str | None = None
    diff_patch: str | None = None
    gate_json: str | None = None
    archive_manifest: str | None = None
    gate_passed: bool = False
    notes: list[str] = field(default_factory=list)


def run_child_round(
    campaign_id: str,
    config_path: str | Path,
    child_id: str | None = None,
    solution_dir: str | Path | None = None,
    parent_id: str = "baseline",
    mode: EvalMode = "pack",
    archive_kind: ArchiveKind = "variant",
    workers: int = 10,
    timeout: int = 3600,
    retry: bool = False,
    version: str | None = None,
    skip_prepare: bool = False,
) -> Path:
    """Run one bounded child round end to end.

    The round performs:

    1. prepare child workspace unless `skip_prepare` is true;
    2. run child evaluation;
    3. gate the child evidence;
    4. archive the evidence as variant when the gate passes, otherwise failed;
    5. write a round report in the child directory.

    `pack` and incomplete local runs are useful smoke tests but normally fail
    the promotion gate because they do not produce full benchmark evidence.
    """
    version = version or now_version()
    child_id = child_id or f"child-{version}"
    root = child_root(campaign_id, child_id)

    report = ChildRoundReport(
        version=version,
        campaign_id=campaign_id,
        child_id=child_id,
        parent_id=parent_id,
        mode=mode,
        requested_archive_kind=archive_kind,
    )

    if not skip_prepare:
        prepared = prepare_child_workspace(
            campaign_id,
            config_path,
            child_id=child_id,
            solution_dir=solution_dir,
            parent_id=parent_id,
            version=version,
        )
        report.prepared_child_json = str(prepared)
    else:
        existing = root / "child.json"
        if not existing.exists():
            raise FileNotFoundError(f"--skip-prepare requested but child.json is missing: {existing}")
        report.prepared_child_json = str(existing)

    child_eval = run_child_evaluation(
        campaign_id,
        child_id,
        mode=mode,
        workers=workers,
        timeout=timeout,
        retry=retry,
        finalize=True,
    )
    report.child_eval_json = str(child_eval)

    evidence_json = root / "result.json"
    diff_patch = root / "diff.patch"
    gate_result: GateResult = gate_evidence(evidence_json, diff_patch)
    gate_json = write_json(root / "gate.json", gate_result)

    final_kind: ArchiveKind = archive_kind
    if archive_kind == "variant" and not gate_result.passed:
        final_kind = "failed"
    manifest = archive_evidence(evidence_json, kind=final_kind, version=version, gate_path=gate_json)

    report.evidence_json = str(evidence_json)
    report.diff_patch = str(diff_patch)
    report.gate_json = str(gate_json)
    report.archive_manifest = str(manifest)
    report.final_archive_kind = final_kind
    report.gate_passed = gate_result.passed
    report.status = "ARCHIVED_VARIANT" if final_kind == "variant" else "ARCHIVED_FAILED" if final_kind == "failed" else "ARCHIVED_BASELINE"
    if not gate_result.passed:
        report.notes.append("Gate failed; candidate was archived as failed evidence.")
    if mode == "pack":
        report.notes.append("Pack mode is a smoke test and is not sufficient for variant promotion.")

    return write_json(root / "round_report.json", report)
