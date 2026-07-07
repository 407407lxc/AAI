from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import campaign_root
from .workflow import utc_now


PROTECTED_PREFIXES = (
    ".aai/archive",
    ".aai/memory",
    "aai_harness/workflow.py",
    "aai_harness/schemas.py",
    "aai_harness/archive.py",
    "aai_harness/memory.py",
    "aai_harness/proposal.py",
    "evaluators",
    "scoring",
    "gates",
)


@dataclass(frozen=True)
class Proposal:
    schema: str
    campaign_id: str
    created_at: str
    title: str
    problem: str
    evidence: dict[str, str]
    proposed_changes: list[str]
    allowed_paths: list[str]
    risks: list[str] = field(default_factory=list)
    acceptance_tests: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProposalReview:
    schema: str
    campaign_id: str
    reviewed_at: str
    decision: str
    reviewer: str
    rationale: str
    accepted_paths: list[str] = field(default_factory=list)
    required_tests: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def proposal_dir(campaign_id: str, root: str | Path | None = None) -> Path:
    return campaign_root(campaign_id, root) / "proposals"


def write_proposal_template(campaign_id: str, root: str | Path | None = None) -> Path:
    out = proposal_dir(campaign_id, root) / "PROPOSALS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out
    out.write_text(
        "# Mode 3 Proposals\n\n"
        "A runtime may propose harness/tooling changes here, but it may not apply them.\n\n"
        "## Proposal template\n\n"
        "- Title:\n"
        "- Problem observed:\n"
        "- Evidence artifacts:\n"
        "- Proposed change:\n"
        "- Allowed paths:\n"
        "- Risks:\n"
        "- Acceptance tests:\n\n"
        "## Protected paths\n\n"
        + "\n".join(f"- `{prefix}`" for prefix in PROTECTED_PREFIXES)
        + "\n",
        encoding="utf-8",
    )
    return out


def create_proposal(
    campaign_id: str,
    title: str,
    problem: str,
    evidence: dict[str, str],
    proposed_changes: list[str],
    allowed_paths: list[str],
    risks: list[str] | None = None,
    acceptance_tests: list[str] | None = None,
    root: str | Path | None = None,
) -> Path:
    proposal = Proposal(
        schema="aai-mode3-proposal.v0",
        campaign_id=campaign_id,
        created_at=utc_now(),
        title=title,
        problem=problem,
        evidence=evidence,
        proposed_changes=proposed_changes,
        allowed_paths=allowed_paths,
        risks=risks or [],
        acceptance_tests=acceptance_tests or [],
    )
    out = proposal_dir(campaign_id, root) / "proposal.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal.to_dict(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return out


def review_proposal(
    campaign_id: str,
    decision: str,
    reviewer: str,
    rationale: str,
    accepted_paths: list[str] | None = None,
    required_tests: list[str] | None = None,
    root: str | Path | None = None,
) -> Path:
    if decision not in {"accepted", "rejected", "needs_revision"}:
        raise ValueError("decision must be one of: accepted, rejected, needs_revision")
    review = ProposalReview(
        schema="aai-mode3-proposal-review.v0",
        campaign_id=campaign_id,
        reviewed_at=utc_now(),
        decision=decision,
        reviewer=reviewer,
        rationale=rationale,
        accepted_paths=accepted_paths or [],
        required_tests=required_tests or [],
    )
    out = proposal_dir(campaign_id, root) / "proposal_review.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(review.to_dict(), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return out


def load_review(campaign_id: str, root: str | Path | None = None) -> dict[str, Any]:
    path = proposal_dir(campaign_id, root) / "proposal_review.json"
    if not path.exists():
        raise FileNotFoundError(f"Proposal review not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_change_allowed(campaign_id: str, changed_paths: list[str], root: str | Path | None = None) -> None:
    review = load_review(campaign_id, root)
    if review.get("decision") != "accepted":
        raise PermissionError("Mode 3 changes require an accepted proposal review.")
    allowed = [p.strip().rstrip("/") for p in review.get("accepted_paths", [])]
    violations = []
    for changed in changed_paths:
        clean = changed.strip().lstrip("./")
        if not any(clean == prefix or clean.startswith(prefix + "/") for prefix in allowed):
            violations.append(clean)
    if violations:
        raise PermissionError(f"Changed paths are outside accepted proposal scope: {violations}")
