from __future__ import annotations

import shutil
from pathlib import Path

from .gates import gate_evidence
from .paths import archive_root, baseline_root, failed_root, variants_root
from .schemas import GateResult, now_version, read_json, write_json


def _copy_optional(src: str | None, dst_dir: Path) -> str | None:
    if not src:
        return None
    src_path = Path(src)
    if not src_path.exists():
        return None
    dst = dst_dir / src_path.name
    if src_path.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src_path, dst)
    else:
        shutil.copy2(src_path, dst)
    return str(dst)


def archive_evidence(
    evidence_path: str | Path,
    kind: str,
    version: str | None = None,
    gate_path: str | Path | None = None,
) -> Path:
    """Archive an evidence record as baseline, variant, or failed run."""
    evidence = read_json(evidence_path)
    task = evidence.get("task") or {}
    definition = task.get("definition") or evidence.get("definition")
    if not definition:
        raise ValueError("evidence does not contain task.definition")
    version = version or evidence.get("version") or now_version()

    if kind == "baseline":
        out_dir = baseline_root(definition) / str(version)
    elif kind == "variant":
        out_dir = variants_root(definition) / f"variant-{version}"
    elif kind == "failed":
        out_dir = failed_root(definition) / f"failed-{version}"
    else:
        raise ValueError("kind must be one of: baseline, variant, failed")

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(evidence_path, out_dir / "evidence.json")
    if gate_path and Path(gate_path).exists():
        shutil.copy2(gate_path, out_dir / "gate.json")

    artifacts = evidence.get("artifacts") or {}
    for key in ["result_json", "retained_log", "diff_patch", "stdout_log", "stderr_log", "audit_json", "solution_snapshot", "config_snapshot"]:
        _copy_optional(artifacts.get(key), out_dir)

    manifest = {
        "schema": "aai-archive-manifest.v1",
        "version": version,
        "kind": kind,
        "definition": definition,
        "source_evidence": str(evidence_path),
        "gate": str(gate_path) if gate_path else None,
        "archive_dir": str(out_dir),
    }
    manifest_path = write_json(out_dir / "manifest.json", manifest)
    update_ledger(definition, f"- `{version}` archived `{kind}` evidence from `{evidence_path}`")
    return manifest_path


def update_ledger(definition: str, entry: str) -> Path:
    path = archive_root(definition) / "harness-ledger.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# AAI Harness Ledger: {definition}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(entry.rstrip() + "\n")
    return path


def update_traps(definition: str, trap: str) -> Path:
    path = archive_root(definition) / "traps" / "TRAPS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# AAI Failure Traps: {definition}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {trap.rstrip()}\n")
    return path


def gate_and_archive(evidence_path: str | Path, kind: str, diff_path: str | Path | None = None, version: str | None = None) -> Path:
    gate: GateResult = gate_evidence(evidence_path, diff_path)
    gate_path = Path(evidence_path).with_name("gate.json")
    write_json(gate_path, gate)
    if kind == "variant" and not gate.passed:
        kind = "failed"
    return archive_evidence(evidence_path, kind=kind, version=version, gate_path=gate_path)
