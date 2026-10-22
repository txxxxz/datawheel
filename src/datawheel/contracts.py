"""The small boundary between the coordinator and domain-specific adapters."""

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Protocol


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n"


def digest(value: Any) -> str:
    return hashlib.sha256(json_text(value).encode()).hexdigest()


@dataclass(frozen=True)
class Record:
    id: str
    group: str
    prompt: str
    response: str
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Any, location: str = "record") -> "Record":
        if not isinstance(value, dict):
            raise ValueError(f"{location}: expected a JSON object")
        allowed = {"id", "group", "prompt", "response", "metadata", "provenance"}
        if set(value) - allowed:
            raise ValueError(f"{location}: unknown fields {sorted(set(value) - allowed)}")
        for key in ("id", "group", "prompt", "response"):
            if not isinstance(value.get(key), str):
                raise ValueError(f"{location}: {key} must be a string")
        for key in ("id", "group"):
            if not value[key].strip() or value[key] != value[key].strip():
                raise ValueError(f"{location}: {key} must be nonempty without outer whitespace")
        for key in ("metadata", "provenance"):
            if not isinstance(value.get(key, {}), dict):
                raise ValueError(f"{location}: {key} must be an object")
        json_text(value)  # Reject non-JSON values and nonfinite numbers at the input boundary.
        return cls(**value)

    def fingerprint(self) -> str:
        return digest({key: value for key, value in asdict(self).items() if key not in ("id", "provenance")})


@dataclass(frozen=True)
class Candidate:
    group: str
    prompt: str
    response: str
    parent_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    passed: bool
    score: float
    reason: str


@dataclass(frozen=True)
class Decision:
    record_id: str
    group: str
    passed: bool
    selected: bool
    score: float
    reason: str


@dataclass(frozen=True)
class Feedback:
    round_index: int
    weights: dict[str, float]
    attempted: dict[str, int]
    failed: dict[str, int]
    reasons: dict[str, dict[str, int]]

    @classmethod
    def initial(cls, groups: list[str]) -> "Feedback":
        return cls(0, dict.fromkeys(groups, 1.0), dict.fromkeys(groups, 0),
                   dict.fromkeys(groups, 0), {group: {} for group in groups})


@dataclass(frozen=True)
class GenerationRequest:
    round_index: int
    seed: int
    allocation: dict[str, int]
    examples: tuple[Record, ...]
    feedback: Feedback


class Adapter(Protocol):
    name: str
    version: str
    mode: str

    def generate(self, request: GenerationRequest) -> list[Candidate]: ...

    def evaluate(self, record: Record) -> Verdict:
        """Return a deterministic, domain-specific judgement, independently of generation."""
        ...
