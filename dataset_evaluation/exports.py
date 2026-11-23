"""Portable JSON and CSV exports for normalized records and aggregates."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping

from .results import EvaluationRecord


_CSV_FIELDS = (
    "run_id",
    "challenge_id",
    "dataset_version",
    "agent_version",
    "model",
    "attempt",
    "status",
    "success",
    "duration_seconds",
    "rounds",
    "tool_calls",
    "token_usage",
    "estimated_cost",
    "failure_type",
    "error_message",
    "category",
)


def export_records_json(path: str | Path, records: Iterable[EvaluationRecord]) -> None:
    """Write normalized, already-redacted records as UTF-8 JSON."""

    payload = [record.as_dict() for record in records]
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_records_csv(path: str | Path, records: Iterable[EvaluationRecord]) -> None:
    """Write a flat CSV while serializing token usage as JSON when present."""

    with Path(path).open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for record in records:
            row = record.as_dict()
            row["token_usage"] = (
                json.dumps(row["token_usage"], sort_keys=True)
                if row["token_usage"] is not None
                else None
            )
            writer.writerow(row)


def export_aggregate_json(path: str | Path, aggregate: Mapping[str, object]) -> None:
    Path(path).write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
