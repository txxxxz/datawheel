"""A deliberately imperfect offline fixture, plus explicit user adapter loading."""

import hashlib
import importlib
import inspect
from pathlib import Path
import random
import re

from .contracts import Adapter, Candidate, GenerationRequest, Record, Verdict, digest


def evaluate_arithmetic(record: Record) -> Verdict:
    match = re.fullmatch(r"(-?\d+)\s*([+*])\s*(-?\d+)", record.prompt)
    if not match:
        return Verdict(False, 0.0, "invalid_expression")
    left, operator, right = match.groups()
    group = {"+": "addition", "*": "multiplication"}[operator]
    if record.group != group:
        return Verdict(False, 0.0, "group_mismatch")
    expected = int(left) + int(right) if operator == "+" else int(left) * int(right)
    correct = record.response == str(expected)
    return Verdict(correct, float(correct), "correct" if correct else "wrong_answer")


class ArithmeticAdapter:
    name = "arithmetic-fixture"
    version = "1"
    mode = "offline-mock"

    evaluate = staticmethod(evaluate_arithmetic)

    def generate(self, request: GenerationRequest) -> list[Candidate]:
        rng = random.Random(request.seed)
        candidates = []
        for group, count in request.allocation.items():
            parents = [record for record in request.examples if record.group == group]
            for index in range(count):
                left, right = rng.randrange(10, 100000), rng.randrange(10, 100000)
                operator = "+" if group == "addition" else "*"
                answer = left + right if operator == "+" else left * right
                # Controlled fixture faults expose the sampler's behavior, not model performance.
                if group == "multiplication" and index % 2 == 0:
                    answer += 1
                candidates.append(Candidate(group, f"{left} {operator} {right}", str(answer),
                                            (rng.choice(parents).id,)))
        return candidates


def load_symbol(spec: str):
    module_name, separator, factory_name = spec.partition(":")
    if not separator or not module_name or not factory_name:
        raise ValueError("Python entry point must be module:name")
    return getattr(importlib.import_module(module_name), factory_name)


def load_adapter(spec: str, config: dict | None = None) -> Adapter:
    if config is not None and not isinstance(config, dict):
        raise ValueError("adapter configuration must be a JSON object")
    factory = load_symbol(spec)
    adapter = factory(config) if config is not None else factory()
    for field in ("name", "version", "mode"):
        if not isinstance(getattr(adapter, field, None), str) or not getattr(adapter, field):
            raise ValueError(f"adapter.{field} must be a nonempty string")
    return adapter


def source_hash(symbol) -> str:
    source = inspect.getsourcefile(symbol)
    if source is None:
        raise ValueError("adapter and evaluator must have readable Python source files for version tracking")
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


def adapter_identity(adapter: Adapter, spec: str, config: dict | None = None) -> dict:
    return {"spec": spec, "name": adapter.name, "version": adapter.version, "mode": adapter.mode,
            "implementation_sha256": source_hash(type(adapter)), "config_sha256": digest(config),
            "dependencies": getattr(adapter, "dependencies", {})}
