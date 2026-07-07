from __future__ import annotations

import json
import os
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import AAI_ROOT, PROJECT_ROOT, campaign_root
from .runtime_logging import RuntimeLogger
from .schemas import now_version, read_json, write_json
from .workspace import child_root

CODEX_CONFIG_PATH = AAI_ROOT / "codex_config.json"
DEFAULT_CODEX_MODEL = "gpt-5.5-codex"


@dataclass(slots=True)
class CodexAgentConfig:
    schema: str = "aai-codex-agent-config.v1"
    version: str = field(default_factory=now_version)
    enabled: bool = True
    codex_bin: str = "codex"
    model: str = DEFAULT_CODEX_MODEL
    api_key_env: str = "CODEX_API_KEY"
    sandbox: str = "workspace-write"
    output_json: bool = True
    ephemeral: bool = True
    ignore_user_config: bool = False
    ignore_rules: bool = False
    timeout: int = 7200
    extra_args: list[str] = field(default_factory=list)
    command_template: str | None = None


@dataclass(slots=True)
class CodexAgentRun:
    schema: str = "aai-codex-agent-run.v1"
    version: str = field(default_factory=now_version)
    campaign_id: str = ""
    child_id: str = ""
    prompt_path: str = ""
    workspace: str = ""
    model: str = DEFAULT_CODEX_MODEL
    status: str = "UNKNOWN"
    command: list[str] = field(default_factory=list)
    runtime_trace: str = ""
    environment_json: str = ""
    stdout_log: str = ""
    stderr_log: str = ""
    final_message_path: str | None = None
    jsonl_path: str | None = None
    returncode: int | None = None
    duration_seconds: float | None = None
    notes: list[str] = field(default_factory=list)


def configure_codex_agent(
    model: str,
    api_key_env: str = "CODEX_API_KEY",
    codex_bin: str = "codex",
    sandbox: str = "workspace-write",
    timeout: int = 7200,
    extra_args: list[str] | None = None,
    command_template: str | None = None,
) -> Path:
    AAI_ROOT.mkdir(parents=True, exist_ok=True)
    cfg = CodexAgentConfig(
        model=model,
        api_key_env=api_key_env,
        codex_bin=codex_bin,
        sandbox=sandbox,
        timeout=timeout,
        extra_args=extra_args or [],
        command_template=command_template,
    )
    return write_json(CODEX_CONFIG_PATH, cfg)


def load_codex_config(config_path: str | Path | None = None) -> CodexAgentConfig:
    path = Path(config_path) if config_path else CODEX_CONFIG_PATH
    if path.exists():
        data = read_json(path)
        return CodexAgentConfig(**{k: v for k, v in data.items() if k in CodexAgentConfig.__dataclass_fields__})
    return CodexAgentConfig()


def codex_is_configured(config_path: str | Path | None = None) -> dict[str, Any]:
    cfg = load_codex_config(config_path)
    return {
        "config_path": str(Path(config_path) if config_path else CODEX_CONFIG_PATH),
        "enabled": cfg.enabled,
        "codex_bin": cfg.codex_bin,
        "model": cfg.model,
        "api_key_env": cfg.api_key_env,
        "api_key_present": bool(os.environ.get(cfg.api_key_env)),
        "sandbox": cfg.sandbox,
        "timeout": cfg.timeout,
    }


def _build_codex_command(cfg: CodexAgentConfig, prompt_path: Path, final_message_path: Path) -> list[str]:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    if cfg.command_template:
        rendered = cfg.command_template.format(
            codex_bin=cfg.codex_bin,
            model=cfg.model,
            sandbox=cfg.sandbox,
            prompt=shlex.quote(prompt_text),
            prompt_path=shlex.quote(str(prompt_path)),
            final_message_path=shlex.quote(str(final_message_path)),
        )
        return shlex.split(rendered)

    cmd = [
        cfg.codex_bin,
        "exec",
        "--sandbox",
        cfg.sandbox,
        "--model",
        cfg.model,
        "--output-last-message",
        str(final_message_path),
    ]
    if cfg.output_json:
        cmd.append("--json")
    if cfg.ephemeral:
        cmd.append("--ephemeral")
    if cfg.ignore_user_config:
        cmd.append("--ignore-user-config")
    if cfg.ignore_rules:
        cmd.append("--ignore-rules")
    cmd.extend(cfg.extra_args)
    cmd.append(prompt_text)
    return cmd


def write_codex_prompt(
    campaign_id: str,
    child_id: str,
    objective: str,
    parent_id: str = "baseline",
    extra_context: str | None = None,
) -> Path:
    root = child_root(campaign_id, child_id)
    root.mkdir(parents=True, exist_ok=True)
    prompt_path = root / "codex_prompt.md"
    body = [
        f"# AAI Codex Child Task: {child_id}",
        "",
        f"- Campaign: `{campaign_id}`",
        f"- Parent: `{parent_id}`",
        f"- Objective: {objective}",
        "",
        "## Required scope",
        "",
        "Edit only the child workspace solution directory unless a Mode 3 proposal has been accepted.",
        "Do not edit evaluator scripts, benchmark data, retained baselines, scoring logic, or AAI archive memory directly.",
        "",
        "## Required evidence",
        "",
        "Update `ITERATIONS.md` with what you tried and why.",
        "Keep `trajectory.json` and `audit.json` consistent with the final candidate.",
        "Do not hide failed attempts; failures are useful evidence for the Master Campaign.",
        "",
        "## Workspace",
        "",
        f"Child root: `{root}`",
        f"Candidate solution path: `{root / 'workspace' / 'solution'}`",
    ]
    if extra_context:
        body.extend(["", "## Additional context", "", extra_context])
    prompt_path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return prompt_path


def run_codex_child_agent(
    campaign_id: str,
    child_id: str,
    prompt_path: str | Path | None = None,
    objective: str | None = None,
    parent_id: str = "baseline",
    config_path: str | Path | None = None,
    timeout: int | None = None,
) -> Path:
    cfg = load_codex_config(config_path)
    root = child_root(campaign_id, child_id)
    runtime_dir = root / "runtime" / f"codex-{now_version()}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    logger = RuntimeLogger(runtime_dir, run_id=f"{campaign_id}/{child_id}/codex")
    logger.write_environment_snapshot(
        {
            "codex": {
                "codex_bin": cfg.codex_bin,
                "model": cfg.model,
                "api_key_env": cfg.api_key_env,
                "api_key_present": bool(os.environ.get(cfg.api_key_env)),
                "sandbox": cfg.sandbox,
            },
            "project_root": str(PROJECT_ROOT),
        }
    )

    if not cfg.enabled:
        run = CodexAgentRun(
            campaign_id=campaign_id,
            child_id=child_id,
            model=cfg.model,
            status="DISABLED",
            runtime_trace=str(logger.trace_path),
            environment_json=str(logger.env_path),
            notes=["Codex agent config is disabled."],
        )
        logger.finish("DISABLED")
        return write_json(root / "codex_agent_run.json", run)

    if not os.environ.get(cfg.api_key_env):
        run = CodexAgentRun(
            campaign_id=campaign_id,
            child_id=child_id,
            model=cfg.model,
            status="MISSING_API_KEY",
            runtime_trace=str(logger.trace_path),
            environment_json=str(logger.env_path),
            notes=[f"Missing API key environment variable: {cfg.api_key_env}"],
        )
        logger.finish("MISSING_API_KEY")
        return write_json(root / "codex_agent_run.json", run)

    prompt = Path(prompt_path) if prompt_path else write_codex_prompt(
        campaign_id,
        child_id,
        objective or "Optimize the child workspace solution while preserving correctness and evidence requirements.",
        parent_id=parent_id,
    )
    final_message_path = runtime_dir / "codex_final_message.md"
    command = _build_codex_command(cfg, prompt, final_message_path)
    env = os.environ.copy()
    if cfg.api_key_env != "CODEX_API_KEY" and cfg.api_key_env in env:
        env["CODEX_API_KEY"] = env[cfg.api_key_env]

    logger.event("codex.invocation", {"prompt_path": str(prompt), "command": command, "cwd": str(root)})
    result = logger.run_command(
        "codex_exec",
        command,
        cwd=root,
        timeout=timeout or cfg.timeout,
        env=env,
    )
    jsonl_path = result.stdout_log if cfg.output_json else None
    status = "CODEX_PASSED" if result.returncode == 0 else "CODEX_FAILED"
    run = CodexAgentRun(
        campaign_id=campaign_id,
        child_id=child_id,
        prompt_path=str(prompt),
        workspace=str(root / "workspace"),
        model=cfg.model,
        status=status,
        command=command,
        runtime_trace=str(logger.trace_path),
        environment_json=str(logger.env_path),
        stdout_log=result.stdout_log,
        stderr_log=result.stderr_log,
        final_message_path=str(final_message_path) if final_message_path.exists() else None,
        jsonl_path=jsonl_path,
        returncode=result.returncode,
        duration_seconds=result.duration_seconds,
    )
    logger.finish(status, {"returncode": result.returncode})
    return write_json(root / "codex_agent_run.json", run)
