"""Transparent aggregate metrics for verified and unverified evaluation runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Iterable

from .results import EvaluationRecord


def _average(values: Iterable[float | int | None]) -> float | None:
    known = [float(value) for value in values if value is not None]
    return mean(known) if known else None


def _summary(records: list[EvaluationRecord]) -> dict[str, object]:
    verified = [record for record in records if record.success is not None]
    successes = [record for record in verified if record.success]
    failures = [record for record in verified if not record.success]
    costs = [record.estimated_cost for record in records if record.estimated_cost is not None]
    failure_counts = Counter(
        record.failure_type for record in records if record.failure_type is not None
    )
    return {
        "runs": len(records),
        "verified_runs": len(verified),
        "successful_runs": len(successes),
        "verified_failures": len(failures),
        "unverified_runs": len(records) - len(verified),
        "success_rate": len(successes) / len(verified) if verified else None,
        "average_duration_seconds": _average(record.duration_seconds for record in records),
        "average_rounds": _average(record.rounds for record in records),
        "average_tool_calls": _average(record.tool_calls for record in records),
        "total_estimated_cost": sum(costs) if costs else None,
        "failure_types": dict(sorted(failure_counts.items())),
    }


def aggregate_records(records: Iterable[EvaluationRecord]) -> dict[str, object]:
    """Produce metrics without treating unverified agent claims as successes."""

    materialized = list(records)
    by_challenge: dict[str, list[EvaluationRecord]] = defaultdict(list)
    by_category: dict[str, list[EvaluationRecord]] = defaultdict(list)
    for record in materialized:
        by_challenge[record.challenge_id].append(record)
        by_category[record.category or "not_available"].append(record)
    return {
        "overall": _summary(materialized),
        "by_challenge": {
            challenge_id: _summary(group)
            for challenge_id, group in sorted(by_challenge.items())
        },
        "by_category": {
            category: _summary(group) for category, group in sorted(by_category.items())
        },
    }
