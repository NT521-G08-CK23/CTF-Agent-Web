"""A minimal, backend-owned lifecycle contract for NYU challenge runs.

It does not replace NYU's loader or Docker lifecycle.  An eventual backend
implementation should call NYU's ``CTFDataset``/``CTFChallenge`` internally,
then implement this narrow public contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from .catalog import ChallengeCatalog, PublicChallenge


@dataclass(frozen=True)
class RuntimeResult:
    run_id: str
    challenge: PublicChallenge
    state: str
    error_code: str | None = None

    def as_dict(self) -> dict[str, object]:
        response: dict[str, object] = {
            "run_id": self.run_id,
            "challenge": self.challenge.as_dict(),
            "state": self.state,
        }
        if self.error_code is not None:
            response["error_code"] = self.error_code
        return response


class ChallengeRuntime(Protocol):
    """Private backend implementation contract; never expose it to the UI."""

    def prepare(self, challenge: PublicChallenge, run_id: str) -> RuntimeResult: ...

    def status(self, run_id: str) -> RuntimeResult: ...

    def cleanup(self, run_id: str) -> RuntimeResult: ...


class UnavailableRuntime:
    """Safe default while Docker/WSL2 or the private NYU checkout is absent."""

    def __init__(self) -> None:
        self._runs: dict[str, RuntimeResult] = {}

    def prepare(self, challenge: PublicChallenge, run_id: str) -> RuntimeResult:
        result = RuntimeResult(
            run_id=run_id,
            challenge=challenge,
            state="unavailable",
            error_code="runtime_unavailable",
        )
        self._runs[run_id] = result
        return result

    def status(self, run_id: str) -> RuntimeResult:
        return self._runs[run_id]

    def cleanup(self, run_id: str) -> RuntimeResult:
        previous = self._runs[run_id]
        result = RuntimeResult(run_id=run_id, challenge=previous.challenge, state="cleaned")
        self._runs[run_id] = result
        return result


class ChallengeRuntimeAdapter:
    """Validate public requests before delegating to a backend-owned runtime."""

    def __init__(self, catalog: ChallengeCatalog, runtime: ChallengeRuntime | None = None):
        self.catalog = catalog
        self.runtime = runtime or UnavailableRuntime()

    def prepare(self, challenge_id: str, run_id: str | None = None) -> RuntimeResult:
        challenge = self.catalog.get(challenge_id)
        safe_run_id = run_id or uuid4().hex
        return self.runtime.prepare(challenge, safe_run_id)

    def status(self, run_id: str) -> RuntimeResult:
        return self.runtime.status(run_id)

    def cleanup(self, run_id: str) -> RuntimeResult:
        return self.runtime.cleanup(run_id)


@dataclass(frozen=True)
class OwnedResource:
    """A resource that was explicitly created by this module for one run."""

    run_id: str
    resource_id: str


class OwnedResourceRegistry:
    """Track only resources this module created; never enumerate global Docker state."""

    def __init__(self) -> None:
        self._resources: dict[str, list[OwnedResource]] = {}

    def register(self, run_id: str, resource_id: str) -> OwnedResource:
        expected_prefix = f"ctf-eval-{run_id}-"
        if not resource_id.startswith(expected_prefix):
            raise ValueError("resource_id must use the module-owned run prefix")
        resource = OwnedResource(run_id=run_id, resource_id=resource_id)
        self._resources.setdefault(run_id, []).append(resource)
        return resource

    def cleanup_candidates(self, run_id: str) -> tuple[OwnedResource, ...]:
        """Return only registered resources for this run, without deleting them."""

        return tuple(self._resources.get(run_id, ()))

    def mark_cleaned(self, run_id: str) -> None:
        self._resources.pop(run_id, None)
