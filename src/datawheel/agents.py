"""Four local roles exchanging typed messages; the coordinator owns persistence."""

from collections import Counter
from dataclasses import asdict, replace
import math
import unicodedata

from .contracts import (Adapter, Decision, Feedback, GenerationBatch, GenerationError,
                        GenerationRequest, Record, Verdict, digest)


def allocate(weights: dict[str, float], budget: int) -> dict[str, int]:
    """Reserve one sample per group, then use largest remainder; ties use group name."""
    if budget < len(weights):
        raise ValueError("budget must allow at least one candidate per group")
    remaining = budget - len(weights)
    shares = {group: remaining * weight / sum(weights.values()) for group, weight in weights.items()}
    counts = {group: 1 + math.floor(share) for group, share in shares.items()}
    order = sorted(weights, key=lambda group: (-(shares[group] % 1), group))
    for group in order[:budget - sum(counts.values())]:
        counts[group] += 1
    return dict(sorted(counts.items()))


class CleanAgent:
    """Normalize outer whitespace and Unicode NFC; reject blank and exact duplicates."""

    def run(self, records: list[Record]) -> tuple[list[Record], list[Decision], list[str]]:
        cleaned, rejected, changed = [], [], []
        seen = set()
        for record in records:
            normalized = replace(record, prompt=unicodedata.normalize("NFC", record.prompt).strip(),
                                 response=unicodedata.normalize("NFC", record.response).strip())
            if normalized != record:
                changed.append(record.id)
            reason = ""
            if not normalized.prompt or not normalized.response:
                reason = "empty_text"
            elif normalized.fingerprint() in seen:
                reason = "duplicate"
            if reason:
                rejected.append(Decision(record.id, record.group, False, False, 0.0, reason))
            else:
                seen.add(normalized.fingerprint())
                cleaned.append(normalized)
        return cleaned, rejected, changed


class SynthesisAgent:
    """Pass the actual feedback and accepted examples to the replaceable generator."""

    def run(self, request: GenerationRequest, adapter: Adapter) -> tuple[list[Record], list[dict]]:
        result = adapter.generate(request)
        candidates = result.candidates if isinstance(result, GenerationBatch) else result
        calls = result.calls if isinstance(result, GenerationBatch) else []
        try:
            return self.materialize(request, adapter, candidates), calls
        except ValueError as error:
            raise GenerationError(str(error), calls) from error

    def materialize(self, request: GenerationRequest, adapter: Adapter, candidates) -> list[Record]:
        if len(candidates) != sum(request.allocation.values()):
            raise ValueError("adapter returned a candidate count different from the requested budget")
        if Counter(candidate.group for candidate in candidates) != Counter(request.allocation):
            raise ValueError("adapter returned groups different from the requested allocation")
        known_ids = {example.id for example in request.examples}
        request_hash = digest(asdict(request))
        records = []
        for index, candidate in enumerate(candidates):
            if not candidate.parent_ids or not set(candidate.parent_ids) <= known_ids:
                raise ValueError("adapter must supply at least one parent_id from the supplied examples")
            record_id = f"r{request.round_index}-{index}-{digest(asdict(candidate))[:12]}"
            if record_id in known_ids:
                raise ValueError(f"generated record id collision: {record_id}")
            records.append(Record.from_dict({
                "id": record_id, "group": candidate.group, "prompt": candidate.prompt,
                "response": candidate.response, "metadata": candidate.metadata,
                "provenance": {"kind": "synthetic", "round": request.round_index,
                               "adapter": adapter.name, "adapter_version": adapter.version,
                               "mode": adapter.mode, "parent_ids": list(candidate.parent_ids),
                               "request_sha256": request_hash},
            }, f"generated candidate {index}"))
        return records


class EvaluationAgent:
    """Apply an independent validator, deduplicate, then rank by score and stable id."""

    def run(self, records: list[Record], existing: list[Record], adapter: Adapter,
            keep: int, min_score: float) -> tuple[list[Record], list[Decision]]:
        seen = {record.fingerprint() for record in existing}
        decisions = []
        for record in records:
            if not record.prompt.strip() or not record.response.strip():
                verdict = Verdict(False, 0.0, "empty_text")
            elif record.fingerprint() in seen:
                verdict = Verdict(False, 0.0, "duplicate")
            else:
                verdict = adapter.evaluate(record)
                if (type(verdict.passed) is not bool or not math.isfinite(verdict.score)
                        or not 0 <= verdict.score <= 1 or not isinstance(verdict.reason, str)
                        or not verdict.reason):
                    raise ValueError("adapter returned an invalid Verdict")
                if verdict.passed and verdict.score < min_score:
                    verdict = Verdict(False, verdict.score, "below_min_score")
            if verdict.passed:
                seen.add(record.fingerprint())
            decisions.append(Decision(record.id, record.group, verdict.passed, False,
                                      verdict.score, verdict.reason))
        winners = sorted((decision for decision in decisions if decision.passed),
                         key=lambda decision: (-decision.score, decision.record_id))[:keep]
        selected_ids = {decision.record_id for decision in winners}
        decisions = [replace(decision, selected=decision.record_id in selected_ids,
                             reason="selection_limit" if decision.passed and decision.record_id not in selected_ids
                             else decision.reason) for decision in decisions]
        selected = sorted((record for record in records if record.id in selected_ids), key=lambda record: record.id)
        return selected, decisions


class FeedbackAgent:
    """Increase effort where cumulative rule failures occur; keep a floor for coverage."""

    def run(self, previous: Feedback, decisions: list[Decision], round_index: int) -> Feedback:
        attempted, failed = previous.attempted.copy(), previous.failed.copy()
        reasons = {group: counts.copy() for group, counts in previous.reasons.items()}
        for decision in decisions:
            attempted[decision.group] += 1
            if not decision.passed:
                failed[decision.group] += 1
                counts = reasons[decision.group]
                counts[decision.reason] = counts.get(decision.reason, 0) + 1
        weights = {group: 1.0 + 3.0 * failed[group] / attempted[group] for group in attempted}
        return Feedback(round_index, weights, attempted, failed, reasons)
