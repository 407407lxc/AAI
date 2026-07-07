from __future__ import annotations

import argparse
from pathlib import Path

from .archive import archive_evidence, gate_and_archive
from .bootstrap import bootstrap_baseline, resolve_task
from .campaign import init_campaign, write_round_prompt
from .child_eval import run_child_evaluation
from .gates import gate_evidence, write_gate_result
from .parent_selection import select_parent
from .paths import ensure_aai_layout
from .proposal import write_proposal_template, write_review
from .workspace import capture_child_diff, finalize_child_evidence, missing_required_child_files, prepare_child_workspace


def cmd_init(args: argparse.Namespace) -> None:
    task = resolve_task(args.config_path, args.solution_dir)
    ensure_aai_layout(task.definition, args.campaign_id)
    print(f"AAI layout initialized for {task.definition}")


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
