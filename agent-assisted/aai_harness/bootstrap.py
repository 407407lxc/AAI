from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import PROJECT_ROOT, default_solution_dir, definition_from_config, ensure_aai_layout, resolve_project_path
from .schemas import ArtifactRefs, EvidenceRecord, Metrics, TaskSpec, now_version, write_json


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _run(cmd: list[str], cwd: Path = PROJECT_ROOT, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)


def resolve_task(config_path: str | Path, solution_dir: str | Path | None = None, runtime: str = "modal") -> TaskSpec:
    cfg_path = resolve_project_path(config_path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.toml not found: {cfg_path}")
    sol_dir = resolve_project_path(solution_dir) if solution_dir else default_solution_dir(cfg_path)
    if not sol_dir.exists():
        raise FileNotFoundError(f"solution directory not found: {sol_dir}")
    return TaskSpec(
        definition=definition_from_config(cfg_path),
        config_path=_relative_to_project(cfg_path),
        solution_dir=_relative_to_project(sol_dir),
        runtime=runtime,  # type: ignore[arg-type]
    )


def pack_candidate(task: TaskSpec, output_path: Path) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "scripts/pack_solution.py",
        "--config-path",
        task.config_path,
        "--solution-dir",
        task.solution_dir,
        "--output",
        str(output_path),
    ]
    return _run(cmd)


def run_local_baseline(task: TaskSpec, timeout: int = 3600) -> subprocess.CompletedProcess[str]:
    if "FIB_DATASET_PATH" not in os.environ:
        raise EnvironmentError("FIB_DATASET_PATH is required for --run-local bootstrap baseline")
    cmd = [
        sys.executable,
        "scripts/run_local.py",
        "--config-path",
        task.config_path,
        "--solution-dir",
        task.solution_dir,
    ]
    return _run(cmd, timeout=timeout)


def bootstrap_baseline(
    config_path: str | Path,
    solution_dir: str | Path | None = None,
    version: str | None = None,
    run_local: bool = False,
    timeout: int = 3600,
) -> Path:
    """Mode 0: validate target, pack current solution, and snapshot baseline evidence."""
    version = version or now_version()
    task = resolve_task(config_path, solution_dir, runtime="local" if run_local else "modal")
    ensure_aai_layout(task.definition)
    out_dir = PROJECT_ROOT / ".aai" / "archive" / task.definition / "baseline" / version
    out_dir.mkdir(parents=True, exist_ok=True)

    packed_path = out_dir / "solution.json"
    pack_proc = pack_candidate(task, packed_path)
    (out_dir / "pack.stdout.log").write_text(pack_proc.stdout or "", encoding="utf-8")
    (out_dir / "pack.stderr.log").write_text(pack_proc.stderr or "", encoding="utf-8")
    if pack_proc.returncode != 0:
        raise RuntimeError(f"pack_solution failed; see {out_dir}")

    config_src = resolve_project_path(task.config_path)
    solution_src = resolve_project_path(task.solution_dir)
    shutil.copy2(config_src, out_dir / "config.toml")
    snapshot = out_dir / "solution_snapshot"
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(solution_src, snapshot)

    stdout_log = stderr_log = None
    status = "PACKED"
    if run_local:
        proc = run_local_baseline(task, timeout=timeout)
        stdout_log = out_dir / "local.stdout.log"
        stderr_log = out_dir / "local.stderr.log"
        stdout_log.write_text(proc.stdout or "", encoding="utf-8")
        stderr_log.write_text(proc.stderr or "", encoding="utf-8")
        status = "LOCAL_PASSED" if proc.returncode == 0 else "LOCAL_FAILED"

    evidence = EvidenceRecord(
        version=version,
        run_id=f"bootstrap-baseline-{version}",
        parent_id="none",
        candidate_id="baseline",
        task=task,
        metrics=Metrics(status=status),
        artifacts=ArtifactRefs(
            result_json=str(packed_path),
            stdout_log=str(stdout_log) if stdout_log else str(out_dir / "pack.stdout.log"),
            stderr_log=str(stderr_log) if stderr_log else str(out_dir / "pack.stderr.log"),
            solution_snapshot=str(snapshot),
            config_snapshot=str(out_dir / "config.toml"),
        ),
        notes=["Mode 0 bootstrap baseline. Existing evaluator scripts are unchanged."],
    )
    return write_json(out_dir / "evidence.json", evidence)
