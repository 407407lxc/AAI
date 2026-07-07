from __future__ import annotations

import argparse
from pathlib import Path

from .archive import archive_evidence, gate_and_archive
from .bootstrap import bootstrap_baseline, resolve_task
from .campaign import init_campaign, write_round_prompt
from .child_eval import run_child_evaluation
from .codex_adapter import codex_is_configured, configure_codex_agent, run_codex_child_agent, write_codex_prompt
from .gates import gate_evidence, write_gate_result
from .memory import update_campaign_memory
from .parent_selection import select_parent
from .paths import ensure_aai_layout
from .proposal import write_proposal_template, write_review
from .round import run_child_round
from .start import start_aai
from .summary import summarize_campaign
from .workspace import capture_child_diff, finalize_child_evidence, missing_required_child_files, prepare_child_workspace


def cmd_init(args: argparse.Namespace) -> None:
    task = resolve_task(args.config_path, args.solution_dir)
    ensure_aai_layout(task.definition, args.campaign_id)
    print(f"AAI layout initialized for {task.definition}")


def cmd_start(args: argparse.Namespace) -> None:
    path = start_aai(
        args.config_path,
        campaign_id=args.campaign_id,
        solution_dir=args.solution_dir,
        codex_model=args.codex_model,
        codex_api_key_env=args.codex_api_key_env,
        codex_bin=args.codex_bin,
        codex_sandbox=args.codex_sandbox,
        codex_timeout=args.codex_timeout,
    )
    print(path)


def cmd_configure_codex(args: argparse.Namespace) -> None:
    path = configure_codex_agent(
        model=args.model,
        api_key_env=args.api_key_env,
        codex_bin=args.codex_bin,
        sandbox=args.sandbox,
        timeout=args.timeout,
        extra_args=args.extra_arg,
        command_template=args.command_template,
    )
    print(path)


def cmd_codex_status(args: argparse.Namespace) -> None:
    print(codex_is_configured(args.config_path))


def cmd_write_codex_prompt(args: argparse.Namespace) -> None:
    path = write_codex_prompt(
        args.campaign_id,
        args.child_id,
        args.objective,
        parent_id=args.parent_id,
        extra_context=args.extra_context,
    )
    print(path)


def cmd_run_codex_agent(args: argparse.Namespace) -> None:
    path = run_codex_child_agent(
        args.campaign_id,
        args.child_id,
        prompt_path=args.prompt_path,
        objective=args.objective,
        parent_id=args.parent_id,
        config_path=args.config_path,
        timeout=args.timeout,
    )
    print(path)


def cmd_bootstrap(args: argparse.Namespace) -> None:
    path = bootstrap_baseline(
        args.config_path,
        solution_dir=args.solution_dir,
        version=args.version,
        run_local=args.run_local,
        timeout=args.timeout,
    )
    print(path)


def cmd_prepare_child(args: argparse.Namespace) -> None:
    path = prepare_child_workspace(
        args.campaign_id,
        args.config_path,
        child_id=args.child_id,
        solution_dir=args.solution_dir,
        parent_id=args.parent_id,
        version=args.version,
    )
    print(path)


def cmd_run_child_eval(args: argparse.Namespace) -> None:
    path = run_child_evaluation(
        args.campaign_id,
        args.child_id,
        mode=args.mode,
        workers=args.workers,
        timeout=args.timeout,
        retry=args.retry,
        finalize=args.finalize,
    )
    print(path)


def cmd_run_child_round(args: argparse.Namespace) -> None:
    path = run_child_round(
        args.campaign_id,
        args.config_path,
        child_id=args.child_id,
        solution_dir=args.solution_dir,
        parent_id=args.parent_id,
        mode=args.mode,
        archive_kind=args.kind,
        workers=args.workers,
        timeout=args.timeout,
        retry=args.retry,
        version=args.version,
        skip_prepare=args.skip_prepare,
    )
    print(path)


def cmd_summarize_campaign(args: argparse.Namespace) -> None:
    json_path, md_path = summarize_campaign(args.campaign_id, metric=args.metric)
    print(json_path)
    print(md_path)


def cmd_update_campaign_memory(args: argparse.Namespace) -> None:
    path = update_campaign_memory(
        args.campaign_id,
        definition=args.definition,
        metric=args.metric,
        min_failure_count=args.min_failure_count,
        write_traps=not args.no_traps,
    )
    print(path)


def cmd_diff_child(args: argparse.Namespace) -> None:
    path = capture_child_diff(args.campaign_id, args.child_id)
    print(path)


def cmd_finalize_child(args: argparse.Namespace) -> None:
    path = finalize_child_evidence(
        args.campaign_id,
        args.child_id,
        benchmark_result_json=args.benchmark_result_json,
        retained_log=args.retained_log,
        stdout_log=args.stdout_log,
        stderr_log=args.stderr_log,
        notes=args.note,
    )
    missing = missing_required_child_files(args.campaign_id, args.child_id)
    if missing:
        print(f"warning: missing required child files: {', '.join(missing)}")
    print(path)


def cmd_select_parent(args: argparse.Namespace) -> None:
    result = select_parent(
        args.definition,
        metric=args.metric,
        allow_failed=args.allow_failed,
        output_path=args.output,
    )
    print(result.get("selected"))


def cmd_gate(args: argparse.Namespace) -> None:
    result = gate_evidence(args.evidence_json, args.diff_patch)
    out = Path(args.output) if args.output else Path(args.evidence_json).with_name("gate.json")
    write_gate_result(out, result)
    print(out)
    if not result.passed:
        raise SystemExit(2)


def cmd_archive(args: argparse.Namespace) -> None:
    manifest = archive_evidence(args.evidence_json, kind=args.kind, version=args.version, gate_path=args.gate_json)
    print(manifest)


def cmd_gate_archive(args: argparse.Namespace) -> None:
    manifest = gate_and_archive(args.evidence_json, kind=args.kind, diff_path=args.diff_patch, version=args.version)
    print(manifest)


def cmd_campaign_init(args: argparse.Namespace) -> None:
    path = init_campaign(args.definition, campaign_id=args.campaign_id, objective=args.objective)
    print(path)


def cmd_round_prompt(args: argparse.Namespace) -> None:
    path = write_round_prompt(
        args.campaign_id,
        args.round_id,
        args.parent_id,
        args.objective,
        constraints=args.constraint,
    )
    print(path)


def cmd_proposal_template(args: argparse.Namespace) -> None:
    print(write_proposal_template(args.campaign_id, args.output))


def cmd_review_proposal(args: argparse.Namespace) -> None:
    path = write_review(args.proposal, args.output)
    print(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AAI harness workflow CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create .aai layout for a config target")
    p.add_argument("--config-path", required=True)
    p.add_argument("--solution-dir")
    p.add_argument("--campaign-id")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("start", help="start an AAI campaign and optionally configure Codex")
    p.add_argument("--config-path", required=True)
    p.add_argument("--solution-dir")
    p.add_argument("--campaign-id")
    p.add_argument("--codex-model")
    p.add_argument("--codex-api-key-env", default="CODEX_API_KEY")
    p.add_argument("--codex-bin", default="codex")
    p.add_argument("--codex-sandbox", default="workspace-write")
    p.add_argument("--codex-timeout", type=int, default=7200)
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("configure-codex", help="write .aai/codex_config.json for Codex CLI automation")
    p.add_argument("--model", required=True)
    p.add_argument("--api-key-env", default="CODEX_API_KEY")
    p.add_argument("--codex-bin", default="codex")
    p.add_argument("--sandbox", default="workspace-write")
    p.add_argument("--timeout", type=int, default=7200)
    p.add_argument("--extra-arg", action="append")
    p.add_argument("--command-template")
    p.set_defaults(func=cmd_configure_codex)

    p = sub.add_parser("codex-status", help="show redacted Codex adapter configuration status")
    p.add_argument("--config-path")
    p.set_defaults(func=cmd_codex_status)

    p = sub.add_parser("write-codex-prompt", help="write a Codex child prompt for a prepared child workspace")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--child-id", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--parent-id", default="baseline")
    p.add_argument("--extra-context")
    p.set_defaults(func=cmd_write_codex_prompt)

    p = sub.add_parser("run-codex-agent", help="run Codex CLI against a prepared child workspace")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--child-id", required=True)
    p.add_argument("--prompt-path")
    p.add_argument("--objective")
    p.add_argument("--parent-id", default="baseline")
    p.add_argument("--config-path")
    p.add_argument("--timeout", type=int)
    p.set_defaults(func=cmd_run_codex_agent)

    p = sub.add_parser("bootstrap", help="Mode 0: validate, pack, and optionally run local baseline")
    p.add_argument("--config-path", required=True)
    p.add_argument("--solution-dir")
    p.add_argument("--version")
    p.add_argument("--run-local", action="store_true")
    p.add_argument("--timeout", type=int, default=3600)
    p.set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("prepare-child", help="create an isolated child workspace seeded from a parent solution")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--config-path", required=True)
    p.add_argument("--child-id")
    p.add_argument("--solution-dir")
    p.add_argument("--parent-id", default="baseline")
    p.add_argument("--version")
    p.set_defaults(func=cmd_prepare_child)

    p = sub.add_parser("run-child-eval", help="run pack/local/modal-full evaluator against a child workspace")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--child-id", required=True)
    p.add_argument("--mode", choices=["pack", "local", "modal-full"], default="pack")
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--retry", action="store_true")
    p.add_argument("--no-finalize", action="store_false", dest="finalize")
    p.set_defaults(func=cmd_run_child_eval, finalize=True)

    p = sub.add_parser("run-child-round", help="prepare, evaluate, gate, and archive one child round")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--config-path", required=True)
    p.add_argument("--child-id")
    p.add_argument("--solution-dir")
    p.add_argument("--parent-id", default="baseline")
    p.add_argument("--mode", choices=["pack", "local", "modal-full"], default="pack")
    p.add_argument("--kind", choices=["baseline", "variant", "failed"], default="variant")
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--retry", action="store_true")
    p.add_argument("--version")
    p.add_argument("--skip-prepare", action="store_true")
    p.set_defaults(func=cmd_run_child_round)

    p = sub.add_parser("summarize-campaign", help="write campaign_summary.json and campaign_summary.md")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--metric", default="avg_latency_ms")
    p.set_defaults(func=cmd_summarize_campaign)

    p = sub.add_parser("update-campaign-memory", help="append campaign summary findings to harness-ledger and TRAPS")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--definition")
    p.add_argument("--metric", default="avg_latency_ms")
    p.add_argument("--min-failure-count", type=int, default=1)
    p.add_argument("--no-traps", action="store_true")
    p.set_defaults(func=cmd_update_campaign_memory)

    p = sub.add_parser("diff-child", help="capture diff.patch between child parent snapshot and candidate workspace")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--child-id", required=True)
    p.set_defaults(func=cmd_diff_child)

    p = sub.add_parser("finalize-child", help="write child result.json EvidenceRecord and refresh diff.patch")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--child-id", required=True)
    p.add_argument("--benchmark-result-json")
    p.add_argument("--retained-log")
    p.add_argument("--stdout-log")
    p.add_argument("--stderr-log")
    p.add_argument("--note", action="append")
    p.set_defaults(func=cmd_finalize_child)

    p = sub.add_parser("select-parent", help="select the best archived parent for a definition")
    p.add_argument("--definition", required=True)
    p.add_argument("--metric", default="avg_latency_ms")
    p.add_argument("--allow-failed", action="store_true")
    p.add_argument("--output")
    p.set_defaults(func=cmd_select_parent)

    p = sub.add_parser("gate", help="validate child evidence before archive/promotion")
    p.add_argument("--evidence-json", required=True)
    p.add_argument("--diff-patch")
    p.add_argument("--output")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("archive", help="archive baseline, variant, or failed evidence")
    p.add_argument("--evidence-json", required=True)
    p.add_argument("--kind", choices=["baseline", "variant", "failed"], required=True)
    p.add_argument("--gate-json")
    p.add_argument("--version")
    p.set_defaults(func=cmd_archive)

    p = sub.add_parser("gate-archive", help="gate evidence, then archive as variant or failed")
    p.add_argument("--evidence-json", required=True)
    p.add_argument("--kind", choices=["baseline", "variant", "failed"], required=True)
    p.add_argument("--diff-patch")
    p.add_argument("--version")
    p.set_defaults(func=cmd_gate_archive)

    p = sub.add_parser("campaign-init", help="create a Master Campaign state directory")
    p.add_argument("--definition", required=True)
    p.add_argument("--campaign-id")
    p.add_argument("--objective", default="latency optimization")
    p.set_defaults(func=cmd_campaign_init)

    p = sub.add_parser("round-prompt", help="write a narrow child-worker prompt")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--round-id", required=True)
    p.add_argument("--parent-id", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--constraint", action="append")
    p.set_defaults(func=cmd_round_prompt)

    p = sub.add_parser("proposal-template", help="write a Mode 3 harness proposal template")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--output")
    p.set_defaults(func=cmd_proposal_template)

    p = sub.add_parser("review-proposal", help="review a Mode 3 proposal for evidence and safety structure")
    p.add_argument("--proposal", required=True)
    p.add_argument("--output")
    p.set_defaults(func=cmd_review_proposal)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
