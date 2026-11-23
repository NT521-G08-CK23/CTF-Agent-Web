"""Trusted exact flag verification, deliberately separate from agent data."""

from __future__ import annotations

import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class FlagVerification:
    """Safe result: it never includes a submitted or expected flag value."""

    matched: bool


def verify_flag_exact(submitted_flag: object, expected_flag: object) -> FlagVerification:
    """Compare values byte-for-byte after UTF-8 encoding; no trimming or heuristics.

    Both values must stay in a trusted backend process.  Callers must persist
    only the boolean result, never either input.
    """

    if (
        not isinstance(submitted_flag, str)
        or not isinstance(expected_flag, str)
        or not submitted_flag
        or not expected_flag
    ):
        return FlagVerification(matched=False)
    return FlagVerification(
        matched=hmac.compare_digest(
            submitted_flag.encode("utf-8"), expected_flag.encode("utf-8")
        )
    )
