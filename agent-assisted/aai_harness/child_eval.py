from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .paths import PROJECT_ROOT
from .runtime_logging import RuntimeLogger
from .schemas import now_version, read_json, write_json
from .workspace import child_root, finalize_child_evidence

EvalMode = Literal["pack", "local", "modal-full"]


@dataclass(slots=True)
class ChildEvalStep:
    name: str
    command: list[str]
    returncode: int
    stdout_log: str
    stderr_log: str
    duration_seconds: float | None = None


@dataclass(slots=True)
class ChildEvalReport:
    schema: str = "aai-child-eval.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    child_id: str = ""
    mode: str = "pack"
    status: str = "UNKNOWN"
    steps: list[ChildEvalStep] = field(default_factory=list)
    artifacts: dict[str, str | None] = field(default_factory=dict)


def _run_step(
    name: str,
    command: list[str],
    log_dir: Path,
    runtime: RuntimeLogger,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> ChildEvalStep:
    result = runtime.run_command(name, command, cwd=PROJECT_ROOT, timeout=timeout, env=env)
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = log_dir / f"{name}.stdout.log"
    stderr_log = log_dir / f"{name}.stderr.log"
    stdout_log.write_text(Path(result.stdout_log).read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    stderr_log.write_text(Path(result.stderr_log).read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    return ChildEvalStep(
        name=name,
        command=command,
        returncode=result.returncode,
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
        duration_seconds=result.duration_seconds,
    )


def _workspace_paths(campaign_id: str, child_id: str) -> tuple[Path, dict]:
    root = child_root(campaign_id, child_id)
    meta_path = root / "child.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"child metadata not found: {meta_path}")
    meta = read_json(meta_path)
    return root, meta["paths"]


def run_child_evaluation(
    campaign_id: str,
    child_id: str,
    mode: EvalMode = "pack",
    workers: int = 10,
    timeout: int = 3600,
    retry: bool = False,
    finalize: bool = True,
) -> Path:
    """Run an evaluator against a child workspace and write child_eval.json.

    The child workspace is expected to have been created with
    `prepare_child_workspace`. This function never edits the repository-level
    solution directory; it points existing evaluator scripts at the child
    workspace config and solution paths.
    """
    root, paths = _workspace_paths(campaign_id, child_id)
    log_dir = root / "logs"
    runtime = RuntimeLogger(root / "runtime" / f"eval-{now_version()}", run_id=f"{campaign_id}/{child_id}/eval")
    runtime.write_environment_snapshot({"mode": mode, "workers": workers, "timeout": timeout, "retry": retry})
    packed_solution = root / "solution.json"
    benchmark_json = root / "benchmark_detailed_results.json"
    retained_log = root / "retained_run.log"

    report = ChildEvalReport(
        campaign_id=campaign_id,
        child_id=child_id,
        mode=mode,
        artifacts={
            "packed_solution": str(packed_solution),
            "benchmark_result_json": str(benchmark_json),
            "retained_log": str(retained_log),
            "result_json": str(root / "result.json"),
            "runtime_trace": str(runtime.trace_path),
            "environment_json": str(runtime.env_path),
        },
    )

    pack_cmd = [
        sys.executable,
        "scripts/pack_solution.py",
        "--config-path",
        paths["workspace_config"],
        "--solution-dir",
        paths["workspace_solution"],
        "--output",
        str(packed_solution),
    ]
    pack_step = _run_step("pack", pack_cmd, log_dir, runtime=runtime, timeout=timeout)
    report.steps.append(pack_step)
    if pack_step.returncode != 0 or mode == "pack":
        report.status = "PACKED" if pack_step.returncode == 0 else "PACK_FAILED"
        eval_report_path = write_json(root / "child_eval.json", asdict(report))
        if finalize:
            finalize_child_evidence(
                campaign_id,
                child_id,
                benchmark_result_json=benchmark_json,
                stdout_log=pack_step.stdout_log,
                stderr_log=pack_step.stderr_log,
                notes=[f"Child evaluation stopped after pack with status {report.status}."],
            )
        runtime.finish(report.status, {"child_eval_json": str(eval_report_path)})
        return eval_report_path

    if mode == "local":
        if "FIB_DATASET_PATH" not in os.environ:
            report.status = "LOCAL_SKIPPED_NO_DATASET"
            runtime.event("eval.skipped", {"reason": "FIB_DATASET_PATH is not set"})
            eval_report_path = write_json(root / "child_eval.json", asdict(report))
            if finalize:
                finalize_child_evidence(
                    campaign_id,
                    child_id,
                    benchmark_result_json=benchmark_json,
                    stdout_log=pack_step.stdout_log,
                    stderr_log=pack_step.stderr_log,
                    notes=["Local child evaluation skipped because FIB_DATASET_PATH is not set."],
                )
            runtime.finish(report.status, {"child_eval_json": str(eval_report_path)})
            return eval_report_path
        local_cmd = [
            sys.executable,
            "scripts/run_local.py",
            "--config-path",
            paths["workspace_config"],
            "--solution-dir",
            paths["workspace_solution"],
        ]
        local_step = _run_step("local", local_cmd, log_dir, runtime=runtime, timeout=timeout)
        report.steps.append(local_step)
        report.status = "LOCAL_PASSED" if local_step.returncode == 0 else "LOCAL_FAILED"
        eval_report_path = write_json(root / "child_eval.json", asdict(report))
        if finalize:
            finalize_child_evidence(
                campaign_id,
                child_id,
                benchmark_result_json=benchmark_json,
                stdout_log=local_step.stdout_log,
                stderr_log=local_step.stderr_log,
                notes=[f"Local child evaluation finished with status {report.status}."],
            )
        runtime.finish(report.status, {"child_eval_json": str(eval_report_path)})
        return eval_report_path

    if mode == "modal-full":
        modal_cmd = [
            sys.executable,
            "scripts/run_modal_multiple_gpus.py",
            "--config-path",
            paths["workspace_config"],
            "--solution-dir",
            paths["workspace_solution"],
            "--out-dir",
            str(root),
            "--workers",
            str(workers),
            "--timeout",
            str(timeout),
        ]
        if retry:
            modal_cmd.append("--retry")
        modal_step = _run_step("modal_full", modal_cmd, log_dir, runtime=runtime, timeout=None)
        report.steps.append(modal_step)
        report.status = "MODAL_PASSED" if modal_step.returncode == 0 else "MODAL_FAILED"
        eval_report_path = write_json(root / "child_eval.json", asdict(report))
        if finalize:
            finalize_child_evidence(
                campaign_id,
                child_id,
                benchmark_result_json=benchmark_json,
                retained_log=retained_log if retained_log.exists() else None,
                stdout_log=modal_step.stdout_log,
                stderr_log=modal_step.stderr_log,
                notes=[f"Modal full child evaluation finished with status {report.status}."],
            )
        runtime.finish(report.status, {"child_eval_json": str(eval_report_path)})
        return eval_report_path

    raise ValueError(f"unsupported child eval mode: {mode}")
