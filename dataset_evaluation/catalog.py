"""Public, allow-listed access to the checked-in NYU pilot manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


class ManifestValidationError(ValueError):
    """Raised when an artifact is not a safe public challenge manifest."""


class ChallengeNotFoundError(KeyError):
    """Raised when a caller requests a challenge outside the allow-list."""


_ROOT_KEYS = {"schema_version", "dataset", "challenges"}
_DATASET_KEYS = {
    "name",
    "source_repository",
    "source_tag",
    "source_commit",
    "split",
    "development_challenge_count",
}
_CHALLENGE_KEYS = {"id", "name", "category", "description", "agent_files"}
_FORBIDDEN_KEY_PARTS = (
    "flag",
    "answer",
    "secret",
    "password",
    "api_key",
    "apikey",
    "token",
    "service",
    "container",
    "internal",
)


@dataclass(frozen=True)
class PublicChallenge:
    """Challenge fields that may be returned to the UI or an agent adapter."""

    id: str
    name: str
    category: str
    description: str
    agent_files: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "agent_files": list(self.agent_files),
        }


@dataclass(frozen=True)
class DatasetIdentity:
    """Public provenance required to make evaluation records reproducible."""

    name: str
    source_repository: str
    source_tag: str
    source_commit: str
    split: str
    development_challenge_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source_repository": self.source_repository,
            "source_tag": self.source_tag,
            "source_commit": self.source_commit,
            "split": self.split,
            "development_challenge_count": self.development_challenge_count,
        }


def _ensure_exact_keys(value: Mapping[str, Any], expected: set[str], where: str) -> None:
    keys = set(value)
    if keys != expected:
        unexpected = sorted(keys - expected)
        missing = sorted(expected - keys)
        raise ManifestValidationError(
            f"{where} must use the public schema exactly; "
            f"unexpected={unexpected}, missing={missing}"
        )
    for key in keys:
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
            raise ManifestValidationError(f"{where}.{key} is not public metadata")


def _valid_agent_file(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in value
        and value == str(path)
    )


def parse_public_manifest(payload: object) -> tuple[DatasetIdentity, tuple[PublicChallenge, ...]]:
    """Validate a manifest and return only its safe, typed representation.

    Raw NYU ``challenge.json`` data must never be passed here: this strict
    schema prevents accidental publication of flags, service settings, and
    other private metadata.
    """

    if not isinstance(payload, Mapping):
        raise ManifestValidationError("manifest root must be an object")
    _ensure_exact_keys(payload, _ROOT_KEYS, "manifest")
    if payload["schema_version"] != "1.0":
        raise ManifestValidationError("unsupported manifest schema_version")

    dataset = payload["dataset"]
    if not isinstance(dataset, Mapping):
        raise ManifestValidationError("dataset must be an object")
    _ensure_exact_keys(dataset, _DATASET_KEYS, "dataset")
    if not all(isinstance(dataset[key], str) and dataset[key] for key in _DATASET_KEYS - {"development_challenge_count"}):
        raise ManifestValidationError("dataset string fields must be non-empty")
    if not isinstance(dataset["development_challenge_count"], int) or dataset["development_challenge_count"] < 1:
        raise ManifestValidationError("development_challenge_count must be a positive integer")
    identity = DatasetIdentity(
        name=dataset["name"],
        source_repository=dataset["source_repository"],
        source_tag=dataset["source_tag"],
        source_commit=dataset["source_commit"],
        split=dataset["split"],
        development_challenge_count=dataset["development_challenge_count"],
    )

    raw_challenges = payload["challenges"]
    if not isinstance(raw_challenges, list) or not raw_challenges:
        raise ManifestValidationError("challenges must be a non-empty array")
    challenges: list[PublicChallenge] = []
    seen_ids: set[str] = set()
    for position, raw_challenge in enumerate(raw_challenges):
        where = f"challenges[{position}]"
        if not isinstance(raw_challenge, Mapping):
            raise ManifestValidationError(f"{where} must be an object")
        _ensure_exact_keys(raw_challenge, _CHALLENGE_KEYS, where)
        for key in ("id", "name", "category", "description"):
            if not isinstance(raw_challenge[key], str) or not raw_challenge[key]:
                raise ManifestValidationError(f"{where}.{key} must be a non-empty string")
        files = raw_challenge["agent_files"]
        if not isinstance(files, list) or not files or not all(_valid_agent_file(item) for item in files):
            raise ManifestValidationError(f"{where}.agent_files must contain safe relative paths")
        challenge_id = raw_challenge["id"]
        if challenge_id in seen_ids:
            raise ManifestValidationError(f"duplicate challenge id: {challenge_id}")
        seen_ids.add(challenge_id)
        challenges.append(
            PublicChallenge(
                id=challenge_id,
                name=raw_challenge["name"],
                category=raw_challenge["category"],
                description=raw_challenge["description"],
                agent_files=tuple(files),
            )
        )
    return identity, tuple(challenges)


class ChallengeCatalog:
    """Read-only catalog for public pilot metadata and allow-listed files."""

    def __init__(self, identity: DatasetIdentity, challenges: tuple[PublicChallenge, ...]):
        self.identity = identity
        self._by_id = {challenge.id: challenge for challenge in challenges}

    @classmethod
    def from_file(cls, path: str | Path) -> "ChallengeCatalog":
        with Path(path).open("r", encoding="utf-8") as manifest_file:
            payload = json.load(manifest_file)
        identity, challenges = parse_public_manifest(payload)
        return cls(identity, challenges)

    def list_public(self) -> list[dict[str, object]]:
        return [challenge.as_dict() for challenge in self._by_id.values()]

    def get(self, challenge_id: str) -> PublicChallenge:
        try:
            return self._by_id[challenge_id]
        except KeyError as error:
            raise ChallengeNotFoundError(challenge_id) from error

    def is_agent_file_allowed(self, challenge_id: str, relative_path: str) -> bool:
        return relative_path in self.get(challenge_id).agent_files
