from __future__ import annotations

from pathlib import Path

from .paths import campaign_root
from .schemas import ProposalReview, now_version, write_json

PROPOSAL_TEMPLATE = """# Mode 3 Harness Proposal

## Evidence

- Failed child ids:
- Logs:
- Repeated failure pattern:
- Why the current harness blocks progress:

## Proposed Change

- Files to change:
- New behavior:
- Backward compatibility:

## Non-goals

- What this must not change:

## Safety / Leakage Risk

- Could this expose hidden eval?
- Could this bias scoring?
- Could this modify baseline?

## Acceptance Test

- Command:
- Expected artifact:
"""

REQUIRED_HEADINGS = [
    "## Evidence",
    "## Proposed Change",
    "## Non-goals",
    "## Safety / Leakage Risk",
    "## Acceptance Test",
]

DANGEROUS_TEXT = [
    "modify baseline",
    "edit benchmark",
    "hidden eval",
    "leaderboard",
    "skip correctness",
    "disable gate",
]


def write_proposal_template(campaign_id: str, output: str | Path | None = None) -> Path:
    out = Path(output) if output else campaign_root(campaign_id) / "proposals" / f"PROPOSALS-{now_version()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PROPOSAL_TEMPLATE, encoding="utf-8")
    return out


def review_proposal(proposal_path: str | Path) -> ProposalReview:
    path = Path(proposal_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    reasons: list[str] = []
    accepted = True

    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            accepted = False
            reasons.append(f"missing required section: {heading}")

    if "Failed child ids:" in text and "- Failed child ids:\n-" not in text:
        accepted = False
        reasons.append("proposal template still appears unfilled; missing concrete failed child ids")

    lowered = text.lower()
    for phrase in DANGEROUS_TEXT:
        if phrase in lowered and "safety" not in lowered:
            accepted = False
            reasons.append(f"dangerous phrase requires explicit safety analysis: {phrase}")

    if "Command:" in text and "Expected artifact:" in text and "```" not in text:
        reasons.append("acceptance test exists but should be made reproducible with exact command block")

    if accepted:
        reasons.append("proposal has the required evidence/safety/reproducibility structure; human/master approval still required")

    return ProposalReview(proposal_path=str(path), accepted=accepted, reasons=reasons)


def write_review(proposal_path: str | Path, output_path: str | Path | None = None) -> Path:
    review = review_proposal(proposal_path)
    out = Path(output_path) if output_path else Path(proposal_path).with_suffix(".review.json")
    return write_json(out, review)
