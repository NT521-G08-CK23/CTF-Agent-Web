"""Safe dataset-catalog and evaluation helpers for CTF-Agent-Web.

This package deliberately exposes public challenge metadata only.  It does
not download NYU CTF Bench, start containers, or expose expected flags.
"""

from .catalog import ChallengeCatalog, PublicChallenge
from .runtime import ChallengeRuntimeAdapter, RuntimeResult

__all__ = [
    "ChallengeCatalog",
    "ChallengeRuntimeAdapter",
    "PublicChallenge",
    "RuntimeResult",
]
