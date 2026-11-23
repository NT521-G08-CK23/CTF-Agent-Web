"""Normalize NYU-style run logs without trusting an agent's solved claim."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping


_FLAG_PATTERN = re.compile(r"(?i)(?:flag|ctf|picoctf)\{[^\r\n}]{0,256}\}")
_API_KEY_PATTERN = re.compile(r"(?i)\b(?:sk|rk|pk)-[a-z0-9_-]{12,}\b")
_NAMED_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_ -]?key|token|password|secret)\s*[:=]\s*[^\s,;]+"
)
_MAX_ERROR_LENGTH = 500


@dataclass(frozen=True)
class EvaluationRecord:
    """Portable evaluation output with explicit unknown/unverified semantics."""

    run_id: str
    challenge_id: str
    dataset_version: str
    agent_version: str | None
    model: str | None
    attempt: int
    status: str
    success: bool | None
    duration_seconds: float | None
    rounds: int | None
    tool_calls: int | None
    token_usage: dict[str, int] | None
    estimated_cost: float | None
    failure_type: str | None
    error_message: str | None
    category: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def redact_text(value: object) -> str | None:
    """Redact likely flags and credentials before a log-derived error is stored."""

    if not isinstance(value, str):
        return None
    result = _FLAG_PATTERN.sub("[REDACTED_FLAG]", value)
    result = _API_KEY_PATTERN.sub("[REDACTED_API_KEY]", result)
    result = _NAMED_SECRET_PATTERN.sub(r"\1=[REDACTED_SECRET]", result)
    return result[:_MAX_ERROR_LENGTH]


def _as_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _as_nonnegative_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0 and math.isfinite(value):
        return float(value)
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _read_first(raw: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _normalize_token_usage(raw: Mapping[str, Any]) -> dict[str, int] | None:
    usage = _mapping(_read_first(raw, "token_usage", "usage"))
    normalized = {
        key: amount
        for key, value in usage.items()
        if (amount := _as_nonnegative_int(value)) is not None
        and key in {"input_tokens", "output_tokens", "total_tokens"}
    }
    return normalized or None


def classify_failure(error_message: str | None) -> str | None:
    """Map an error to a coarse operational taxonomy without asserting cause."""

    if not error_message:
        return None
    value = error_message.lower()
    if "timeout" in value or "timed out" in value:
        return "timeout"
    if any(term in value for term in ("not found", "missing file", "no such file")):
        return "missing_data"
    if any(term in value for term in ("docker", "container", "network", "connection refused")):
        return "challenge_environment"
    if any(term in value for term in ("configuration", "config", "permission denied")):
        return "configuration"
    if any(term in value for term in ("model", "api", "rate limit")):
        return "model"
    if any(term in value for term in ("tool", "command", "sandbox")):
        return "tool"
    return "agent"


def normalize_baseline_log(
    raw_log: Mapping[str, Any],
    *,
    run_id: str,
    challenge_id: str,
    dataset_version: str,
    agent_version: str | None = None,
    attempt: int = 1,
    category: str | None = None,
    flag_verified: bool | None = None,
) -> EvaluationRecord:
    """Normalize a NYU-baseline-compatible log using trusted verification state.

    ``raw_log['solved']`` is deliberately ignored for success.  A value is a
    success only when ``flag_verified`` is ``True`` from the trusted checker;
    an agent claim with no verifier result remains ``unverified``.
    """

    if attempt < 1:
        raise ValueError("attempt must be at least 1")
    args = _mapping(raw_log.get("args"))
    runtime = _mapping(raw_log.get("runtime"))
    error_message = redact_text(_read_first(raw_log, "error_message", "error", "exception"))
    model_value = _read_first(raw_log, "model") or _read_first(args, "model")
    model = model_value if isinstance(model_value, str) and model_value else None
    duration = _as_nonnegative_float(
        _read_first(raw_log, "duration_seconds", "time_taken", "runtime_seconds")
    )
    if duration is None:
        duration = _as_nonnegative_float(runtime.get("total"))
    rounds = _as_nonnegative_int(_read_first(raw_log, "rounds"))
    tool_calls = _as_nonnegative_int(_read_first(raw_log, "tool_calls"))
    if tool_calls is None:
        tool_calls = _as_nonnegative_int(runtime.get("tool_calls"))
    if tool_calls is None:
        tools_value = runtime.get("tools")
        if isinstance(tools_value, list):
            tool_calls = len(tools_value)
    cost = _as_nonnegative_float(_read_first(raw_log, "estimated_cost", "cost", "total_cost"))

    if flag_verified is True:
        status, success, failure_type = "verified_success", True, None
    elif flag_verified is False:
        status, success, failure_type = "verified_failure", False, "wrong_flag"
    elif error_message:
        status, success, failure_type = "error", None, classify_failure(error_message)
    else:
        status, success, failure_type = "unverified", None, None

    return EvaluationRecord(
        run_id=run_id,
        challenge_id=challenge_id,
        dataset_version=dataset_version,
        agent_version=agent_version,
        model=model,
        attempt=attempt,
        status=status,
        success=success,
        duration_seconds=duration,
        rounds=rounds,
        tool_calls=tool_calls,
        token_usage=_normalize_token_usage(raw_log),
        estimated_cost=cost,
        failure_type=failure_type,
        error_message=error_message,
        category=category,
    )
