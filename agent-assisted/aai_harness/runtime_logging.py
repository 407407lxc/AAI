from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

from .schemas import now_version

SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL")


@dataclass(slots=True)
class CommandResult:
    name: str
    command: list[str]
    cwd: str
    returncode: int
    duration_seconds: float
    stdout_log: str
    stderr_log: str
    started_at: str
    finished_at: str


@dataclass(slots=True)
class RuntimeLogConfig:
    root: str
    trace_path: str
    env_path: str
    command_dir: str
    started_at: str = field(default_factory=now_version)


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def redact_value(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    upper = key.upper()
    if any(marker in upper for marker in SECRET_MARKERS):
        return "<redacted:set>" if value else "<redacted:empty>"
    return value


def redact_env(env: dict[str, str] | None = None) -> dict[str, str]:
    source = env if env is not None else dict(os.environ)
    return {key: redact_value(key, value) or "" for key, value in sorted(source.items())}


class RuntimeLogger:
    """Append-only runtime trace logger for AAI runs.

    The logger writes JSONL events plus command stdout/stderr files. It never
    writes secret values; environment snapshots are redacted by key name.
    """

    def __init__(self, root: str | Path, run_id: str | None = None) -> None:
        self.root = Path(root)
        self.run_id = run_id or now_version()
        self.root.mkdir(parents=True, exist_ok=True)
        self.command_dir = self.root / "commands"
        self.command_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.root / "runtime_trace.jsonl"
        self.env_path = self.root / "environment.json"
        self.config = RuntimeLogConfig(
            root=str(self.root),
            trace_path=str(self.trace_path),
            env_path=str(self.env_path),
            command_dir=str(self.command_dir),
        )
        self.event("runtime.started", {"run_id": self.run_id, "config": self.config})

    def event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        record = {
            "ts": now_version(),
            "run_id": self.run_id,
            "type": event_type,
            "payload": payload or {},
        }
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n")

    def write_environment_snapshot(self, extra: dict[str, Any] | None = None) -> Path:
        payload = {
            "schema": "aai-runtime-environment.v1",
            "version": now_version(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            },
            "env": redact_env(),
            "extra": extra or {},
        }
        self.env_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.event("runtime.environment", {"path": str(self.env_path)})
        return self.env_path

    def run_command(
        self,
        name: str,
        command: list[str],
        cwd: str | Path,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
        stdin: str | None = None,
    ) -> CommandResult:
        started = now_version()
        started_mono = time.monotonic()
        stdout_log = self.command_dir / f"{name}.stdout.log"
        stderr_log = self.command_dir / f"{name}.stderr.log"
        safe_env = redact_env(env or os.environ.copy())
        self.event(
            "command.started",
            {
                "name": name,
                "command": command,
                "cwd": str(cwd),
                "timeout": timeout,
                "env": safe_env,
            },
        )
        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd),
                text=True,
                input=stdin,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
            returncode = proc.returncode
            stdout_text = proc.stdout or ""
            stderr_text = proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            returncode = 124
            stdout_text = exc.stdout or ""
            stderr_text = (exc.stderr or "") + f"\nCommand timed out after {timeout} seconds."
            self.event("command.timeout", {"name": name, "timeout": timeout})
        except OSError as exc:
            returncode = 127
            stdout_text = ""
            stderr_text = f"Command failed to start: {exc}"
            self.event("command.start_failed", {"name": name, "error": str(exc)})
        finished = now_version()
        duration = time.monotonic() - started_mono
        stdout_log.write_text(stdout_text, encoding="utf-8")
        stderr_log.write_text(stderr_text, encoding="utf-8")
        result = CommandResult(
            name=name,
            command=command,
            cwd=str(cwd),
            returncode=returncode,
            duration_seconds=duration,
            stdout_log=str(stdout_log),
            stderr_log=str(stderr_log),
            started_at=started,
            finished_at=finished,
        )
        self.event("command.completed", {"result": result})
        return result

    def finish(self, status: str, payload: dict[str, Any] | None = None) -> None:
        self.event("runtime.finished", {"status": status, **(payload or {})})
