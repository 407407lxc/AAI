"""Runtime adapters for AAI phase execution.

Adapters are phase-local. They may produce evidence, but they must not advance
the global AAI workflow or write archive/memory/proposal approvals directly.
"""

from .base import PhaseRunResult, RuntimeAdapter
from .manual import ManualRuntimeAdapter

__all__ = ["PhaseRunResult", "RuntimeAdapter", "ManualRuntimeAdapter"]
