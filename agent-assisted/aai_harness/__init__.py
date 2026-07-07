"""Agentic AI harness support for the FlashInfer contest package.

The package intentionally sits beside the existing benchmark scripts.  It wraps
packing, evaluation, evidence collection, gating, archival, campaign planning,
and proposal review without changing the official evaluator path.
"""

from .schemas import VERSION_SCHEMA, now_version

__all__ = ["VERSION_SCHEMA", "now_version"]
