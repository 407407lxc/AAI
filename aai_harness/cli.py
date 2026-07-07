from __future__ import annotations

import argparse
import json

from .archive import archive_run
from .memory import write_memory_update
from .proposal import create_proposal, review_proposal, write_proposal_template
from .workflow import (
    advance_campaign,
    allowed_actions,
    ensure_campaign_dirs,
    export_contract,
    init_campaign,
    load_campaign,
)


def parse_artifact_pairs(values: list[str] | None) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"Artifact must use name=path format, got: {item}")
        name, path = item.split("=", 1)
        artifacts[name.strip()] = path.strip()
    return artifacts


def parse_list(values: list[str] | None) -> list[str]:
    return [item for item in (values or []) if item]


def cmd_init(args: argparse.Namespace) -> None:
    path = init_campaign(args.campaign_id, args.objective, args.root)
    ensure_campaign_dirs(args.campaign_id, args.root)
    print(path)


def cmd_advance(args: argparse.Namespace) -> None:
    artifacts = parse_artifact_pairs(args.artifact)
    path = advance_campaign(
        campaign_id=args.campaign_id,
        action=args.action,
        artifacts=artifacts,
        notes=args.notes or "",
        actor=args.actor,
        root=args.root,
        require_existing_files=not args.no_file_check,
    )
    print(path)


def cmd_status(args: argparse.Namespace) -> None:
    record = load_campaign(args.campaign_id, args.root)
    record["allowed_actions"] = allowed_actions(args.campaign_id, args.root)
    print(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True))


def cmd_contract(args: argparse.Namespace) -> None:
    print(json.dumps(export_contract(), indent=2, ensure_ascii=False, sort_keys=True))


def cmd_archive(args: argparse.Namespace) -> None:
    artifacts = parse_artifact_pairs(args.artifact)
    path = archive_run(
        campaign_id=args.campaign_id,
        archive_type=args.archive_type,
        artifacts=artifacts,
        root=args.root,
        notes=args.notes or "",
        copy_artifacts=not args.no_copy,
    )
    print(path)


def cmd_memory(args: argparse.Namespace) -> None:
    evidence = parse_artifact_pairs(args.evidence)
    path = write_memory_update(
        campaign_id=args.campaign_id,
        outcome=args.outcome,
        summary=args.summary,
        lessons=parse_list(args.lesson),
        traps=parse_list(args.trap),
        next_actions=parse_list(args.next_action),
        evidence=evidence,
        root=args.root,
    )
    print(path)


def cmd_proposal_template(args: argparse.Namespace) -> None:
    print(write_proposal_template(args.campaign_id, args.root))


def cmd_create_proposal(args: argparse.Namespace) -> None:
    evidence = parse_artifact_pairs(args.evidence)
    print(create_proposal(
        campaign_id=args.campaign_id,
        title=args.title,
        problem=args.problem,
        evidence=evidence,
        proposed_changes=parse_list(args.change),
        allowed_paths=parse_list(args.allowed_path),
        risks=parse_list(args.risk),
        acceptance_tests=parse_list(args.acceptance_test),
        root=args.root,
    ))


def cmd_review_proposal(args: argparse.Namespace) -> None:
    print(review_proposal(
        campaign_id=args.campaign_id,
        decision=args.decision,
        reviewer=args.reviewer,
        rationale=args.rationale,
        accepted_paths=parse_list(args.accepted_path),
        required_tests=parse_list(args.required_test),
        root=args.root,
    ))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AAI external workflow control plane.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-campaign")
    init.add_argument("--campaign-id", required=True)
    init.add_argument("--objective", required=True)
    init.add_argument("--root")
    init.set_defaults(func=cmd_init)

    advance = sub.add_parser("advance")
    advance.add_argument("--campaign-id", required=True)
    advance.add_argument("--action", required=True)
    advance.add_argument("--artifact", action="append", help="Artifact in name=path form. Repeatable.")
    advance.add_argument("--notes")
    advance.add_argument("--actor", default="human", choices=["human", "master", "runtime", "system"])
    advance.add_argument("--root")
    advance.add_argument("--no-file-check", action="store_true")
    advance.set_defaults(func=cmd_advance)

    status = sub.add_parser("status")
    status.add_argument("--campaign-id", required=True)
    status.add_argument("--root")
    status.set_defaults(func=cmd_status)

    contract = sub.add_parser("contract")
    contract.set_defaults(func=cmd_contract)

    archive = sub.add_parser("archive")
    archive.add_argument("--campaign-id", required=True)
    archive.add_argument("--archive-type", required=True, choices=["variant", "failed", "baseline", "manual"])
    archive.add_argument("--artifact", action="append", help="Artifact in name=path form. Repeatable.")
    archive.add_argument("--notes")
    archive.add_argument("--root")
    archive.add_argument("--no-copy", action="store_true")
    archive.set_defaults(func=cmd_archive)

    memory = sub.add_parser("memory-update")
    memory.add_argument("--campaign-id", required=True)
    memory.add_argument("--outcome", required=True)
    memory.add_argument("--summary", required=True)
    memory.add_argument("--lesson", action="append")
    memory.add_argument("--trap", action="append")
    memory.add_argument("--next-action", action="append")
    memory.add_argument("--evidence", action="append", help="Evidence in name=path form. Repeatable.")
    memory.add_argument("--root")
    memory.set_defaults(func=cmd_memory)

    proposal_template = sub.add_parser("proposal-template")
    proposal_template.add_argument("--campaign-id", required=True)
    proposal_template.add_argument("--root")
    proposal_template.set_defaults(func=cmd_proposal_template)

    proposal = sub.add_parser("create-proposal")
    proposal.add_argument("--campaign-id", required=True)
    proposal.add_argument("--title", required=True)
    proposal.add_argument("--problem", required=True)
    proposal.add_argument("--evidence", action="append", help="Evidence in name=path form. Repeatable.")
    proposal.add_argument("--change", action="append", required=True)
    proposal.add_argument("--allowed-path", action="append", required=True)
    proposal.add_argument("--risk", action="append")
    proposal.add_argument("--acceptance-test", action="append")
    proposal.add_argument("--root")
    proposal.set_defaults(func=cmd_create_proposal)

    review = sub.add_parser("review-proposal")
    review.add_argument("--campaign-id", required=True)
    review.add_argument("--decision", required=True, choices=["accepted", "rejected", "needs_revision"])
    review.add_argument("--reviewer", required=True)
    review.add_argument("--rationale", required=True)
    review.add_argument("--accepted-path", action="append")
    review.add_argument("--required-test", action="append")
    review.add_argument("--root")
    review.set_defaults(func=cmd_review_proposal)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
