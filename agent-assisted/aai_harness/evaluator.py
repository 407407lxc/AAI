from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .paths import PROJECT_ROOT
from .schemas import now_version


def run_modal_single(
    config_path: str,
    workload_uuid: str,
    solution_dir: str | None = None,
    official: bool = True,
    profile_torch: bool = False,
    profile_ncu: bool = False,
    timeout: int = 7200,
) -> subprocess.CompletedProcess[str]:
    """Run the existing single-workload Modal evaluator.

    This wrapper intentionally delegates to scripts/run_modal_single.py so the
    AAI layer does not become a second source of evaluator truth.
    """
    cmd = [
        sys.executable,
        "-m",
        "modal",
        "run",
        "scripts/run_modal_single.py",
        "--workload-uuid",
        workload_uuid,
        "--config-path",
        config_path,
    ]
    if solution_dir:
        cmd.extend(["--solution-dir", solution_dir])
    if official:
        cmd.append("--official")
    if profile_torch:
        cmd.append("--profile-torch")
    if profile_ncu:
        cmd.append("--profile-ncu")
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True, capture_output=True, timeout=timeout)


def run_modal_full(
    config_path: str,
    out_dir: str,
    workers: int = 10,
    solution_dir: str | None = None,
    retry: bool = False,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run the existing multi-workload Modal evaluator."""
    cmd = [
        sys.executable,
        "scripts/run_modal_multiple_gpus.py",
        "--config-path",
        config_path,
        "--out-dir",
        out_dir,
        "--workers",
        str(workers),
        "--timeout",
        str(timeout),
    ]
    if solution_dir:
        cmd.extend(["--solution-dir", solution_dir])
    if retry:
        cmd.append("--retry")
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True, capture_output=True)


def save_process_logs(proc: subprocess.CompletedProcess[str], log_dir: Path, prefix: str | None = None) -> tuple[Path, Path]:
    prefix = prefix or now_version()
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / f"{prefix}.stdout.log"
    stderr = log_dir / f"{prefix}.stderr.log"
    stdout.write_text(proc.stdout or "", encoding="utf-8")
    stderr.write_text(proc.stderr or "", encoding="utf-8")
    return stdout, stderr
