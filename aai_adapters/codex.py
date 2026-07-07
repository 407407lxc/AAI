from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import PhaseRunResult, write_phase_result


@dataclass(frozen=True)
class CodexPhaseSpec:
    campaign_id: str
    workspace: str
    prompt_path: str
    output_path: str
    codex_bin: str = "codex"
    model: str | None = None
    sandbox: str = "workspace-write"
    timeout_s: int = 7200
    dry_run: bool = False


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CodexPhaseAdapter:
    """Run Codex as a bounded phase-local executor.

    Codex receives a workspace and prompt file. The prompt text is not persisted
    in the command record; only prompt path and sha256 are stored. Codex may
    produce evidence, but AAI validates and advances the outer workflow.
    """

    runtime_name = "codex"

    def build_command(self, spec: CodexPhaseSpec, final_message_path: Path) -> list[str]:
        command = [spec.codex_bin, "exec", "--sandbox", spec.sandbox, "--output-last-message", str(final_message_path)]
        if spec.model:
            command.extend(["--model", spec.model])
        command.append(Path(spec.prompt_path).read_text(encoding="utf-8"))
        return command

    def run_phase(self, phase_spec: dict[str, Any]) -> PhaseRunResult:
        spec = CodexPhaseSpec(
            campaign_id=str(phase_spec["campaign_id"]),
            workspace=str(phase_spec["workspace"]),
            prompt_path=str(phase_spec["prompt_path"]),
            output_path=str(phase_spec.get("output_path", ".aai/codex_phase_result.json")),
            codex_bin=str(phase_spec.get("codex_bin", "codex")),
            model=phase_spec.get("model"),
            sandbox=str(phase_spec.get("sandbox", "workspace-write")),
            timeout_s=int(phase_spec.get("timeout_s", 7200)),
            dry_run=bool(phase_spec.get("dry_run", False)),
        )
        workspace = Path(spec.workspace).resolve()
        prompt_path = Path(spec.prompt_path).resolve()
        output_path = Path(spec.output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_message = output_path.with_suffix(".final_message.md")
        stdout = output_path.with_suffix(".stdout.log")
        stderr = output_path.with_suffix(".stderr.log")

        prompt_text = prompt_path.read_text(encoding="utf-8")
        prompt_sha = sha256_text(prompt_text)
        metadata: dict[str, Any] = {
            "workspace": str(workspace),
            "prompt_path": str(prompt_path),
            "prompt_sha256": prompt_sha,
            "codex_bin": spec.codex_bin,
            "model": spec.model,
            "sandbox": spec.sandbox,
            "dry_run": spec.dry_run,
        }
        logs: dict[str, str] = {}

        if spec.dry_run:
            status = "DRY_RUN"
        elif not workspace.exists():
            status = "MISSING_WORKSPACE"
        elif not os.environ.get("CODEX_API_KEY"):
            status = "MISSING_CODEX_API_KEY"
        else:
            command = self.build_command(spec, final_message)
            metadata["command_shape"] = [command[0], "exec", "--sandbox", spec.sandbox, "--output-last-message", str(final_message), "<prompt_text_redacted>"]
            proc = subprocess.run(
                command,
                cwd=str(workspace),
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

        evidence: dict[str, str] = {"prompt": str(prompt_path)}
        if final_message.exists():
            evidence["final_message"] = str(final_message)
        result = PhaseRunResult(
            schema="aai-phase-run-result.v0",
            campaign_id=spec.campaign_id,
            runtime_name=self.runtime_name,
            status=status,
            evidence=evidence,
            logs=logs,
            notes="Codex was run as a bounded phase-local executor.",
            metadata=metadata,
        )
        write_phase_result(output_path, result)
        return result


def run_from_file(path: str | Path) -> Path:
    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    adapter = CodexPhaseAdapter()
    result = adapter.run_phase(spec)
    output_path = Path(spec.get("output_path", ".aai/codex_phase_result.json"))
    if not output_path.exists():
        write_phase_result(output_path, result)
    return output_path
