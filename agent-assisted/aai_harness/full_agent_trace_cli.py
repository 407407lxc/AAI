from __future__ import annotations

import argparse

from .full_agent_trace import init_full_agent_trace, render_trace_tree, sync_full_agent_trace, trace_status


def cmd_init(args: argparse.Namespace) -> None:
    path = init_full_agent_trace(args.campaign_id, args.definition, objective=args.objective)
    print(path)


def cmd_sync(args: argparse.Namespace) -> None:
    path = sync_full_agent_trace(args.campaign_id, args.definition, args.iteration, child_id=args.child_id)
    print(path)


def cmd_status(args: argparse.Namespace) -> None:
    print(trace_status(args.campaign_id))


def cmd_tree(args: argparse.Namespace) -> None:
    print(render_trace_tree(args.campaign_id))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AAI full-agent-style trace mirror CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="initialize full-agent-style trace tree for a campaign")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--definition", required=True)
    p.add_argument("--objective")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("sync", help="mirror current AAI artifacts into full-agent-style trace layout")
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--definition", required=True)
    p.add_argument("--iteration", type=int, required=True)
    p.add_argument("--child-id")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("status", help="show trace index status")
    p.add_argument("--campaign-id", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("tree", help="print full-agent-style trace tree")
    p.add_argument("--campaign-id", required=True)
    p.set_defaults(func=cmd_tree)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
