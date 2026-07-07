from __future__ import annotations

import argparse
import json

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

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
