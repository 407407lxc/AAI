from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .bootstrap import resolve_task
from .campaign import init_campaign
from .codex_adapter import codex_is_configured, configure_codex_agent
from .paths import campaign_root, ensure_aai_layout
from .runtime_logging import RuntimeLogger
from .schemas import now_version, write_json


@dataclass(slots=True)
class AAIStartReport:
    schema: str = "aai-start-report.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    definition: str = ""
    config_path: str = ""
    solution_dir: str = ""
    codex: dict = field(default_factory=dict)
    runtime_trace: str = ""
    environment_json: str = ""
    status: str = "UNKNOWN"
    notes: list[str] = field(default_factory=list)


def start_aai(
    config_path: str | Path,
    campaign_id: str | None = None,
    solution_dir: str | Path | None = None,
    codex_model: str | None = None,
    codex_api_key_env: str = "CODEX_API_KEY",
    codex_bin: str = "codex",
    codex_sandbox: str = "workspace-write",
    codex_timeout: int = 7200,
) -> Path:
    task = resolve_task(config_path, solution_dir)
    campaign_id = campaign_id or f"campaign-{now_version()}"
    ensure_aai_layout(task.definition, campaign_id)
    init_campaign(task.definition, campaign_id=campaign_id, objective="AAI Codex-backed optimization campaign")

    if codex_model:
        configure_codex_agent(
            model=codex_model,
            api_key_env=codex_api_key_env,
            codex_bin=codex_bin,
            sandbox=codex_sandbox,
            timeout=codex_timeout,
        )

    root = campaign_root(campaign_id)
    runtime = RuntimeLogger(root / "runtime" / f"start-{now_version()}", run_id=f"{campaign_id}/start")
    runtime.write_environment_snapshot({"task": task, "codex_api_key_env": codex_api_key_env})
    codex_status = codex_is_configured()
    status = "READY" if codex_status.get("enabled") and codex_status.get("api_key_present") else "READY_NO_CODEX_KEY"
    notes = []
    if status == "READY_NO_CODEX_KEY":
        notes.append(f"Codex config exists but API key env var is not set: {codex_status.get('api_key_env')}")
    report = AAIStartReport(
        campaign_id=campaign_id,
        definition=task.definition,
        config_path=task.config_path,
        solution_dir=task.solution_dir,
        codex=codex_status,
        runtime_trace=str(runtime.trace_path),
        environment_json=str(runtime.env_path),
        status=status,
        notes=notes,
    )
    runtime.finish(status, {"campaign_id": campaign_id, "definition": task.definition})
    return write_json(root / "aai_start.json", report)
