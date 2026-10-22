"""An explicit coordinator: each role consumes the previous role's saved message."""

from collections import Counter
from dataclasses import asdict
import hashlib
from pathlib import Path

from . import __version__
from .adapters import adapter_identity, load_adapter
from .agents import CleanAgent, EvaluationAgent, FeedbackAgent, SynthesisAgent, allocate
from .contracts import Feedback, GenerationRequest, digest, json_text
from .store import atomic_write, commit_directory, jsonl_text, read_json, read_records, sha256_file, verify_commit


DEFAULT_ADAPTER = "datawheel.tool_dialogue:ToolDialogueAdapter"


def engine_hash() -> str:
    sources = {path.name: sha256_file(path) for path in sorted(Path(__file__).parent.glob("*.py"))}
    return digest(sources)


def message(sender: str, recipient: str, kind: str, artifact: str) -> dict:
    return {"sender": sender, "recipient": recipient, "kind": kind, "artifact": artifact}


def prepare_seed(input_path: Path, output: Path, manifest: dict) -> str:
    records = read_records(input_path, manifest["source_sha256"])
    cleaned, rejected, changed = CleanAgent().run(records)
    adapter = load_adapter(manifest["adapter"]["spec"])
    admitted, decisions = EvaluationAgent().run(cleaned, [], adapter, len(cleaned), manifest["config"]["min_score"])
    if not admitted:
        raise ValueError("no seed records passed cleaning and domain validation")
    groups = sorted({record.group for record in admitted})
    allocate(dict.fromkeys(groups, 1.0), manifest["config"]["budget"])
    report = {"input_records": len(records), "normalized_ids": changed, "admitted": len(admitted),
              "rejected": len(records) - len(admitted),
              "reasons": dict(Counter(decision.reason for decision in rejected + decisions if not decision.passed)),
              "groups": groups}
    return commit_directory(output / "seed", {
        "records.jsonl": jsonl_text(asdict(record) for record in admitted),
        "decisions.jsonl": jsonl_text(asdict(decision) for decision in rejected + decisions),
        "report.json": json_text(report),
        "messages.jsonl": jsonl_text([
            message("importer", "cleaner", "imported_records", "../manifest.json"),
            message("cleaner", "evaluator", "normalization_and_rejections", "report.json"),
            message("evaluator", "synthesizer", "admitted_seeds", "records.jsonl"),
        ]),
    }, digest(manifest))


def round_report(index: int, allocation: dict, decisions: list, feedback: Feedback, budget: int) -> dict:
    groups = {}
    for group in allocation:
        subset = [decision for decision in decisions if decision.group == group]
        groups[group] = {"generated": len(subset), "passed": sum(decision.passed for decision in subset),
                         "selected": sum(decision.selected for decision in subset),
                         "failures": dict(Counter(decision.reason for decision in subset if not decision.passed))}
    return {"round": index, "allocation": allocation, "groups": groups,
            "passed": sum(decision.passed for decision in decisions),
            "selected": sum(decision.selected for decision in decisions),
            "next_weights": feedback.weights, "next_allocation": allocate(feedback.weights, budget)}


def run(input_path: str | Path, output: str | Path, *, rounds: int = 2, budget: int = 12,
        keep: int = 8, seed: int = 7, min_score: float = 1.0,
        adapter_spec: str = DEFAULT_ADAPTER, resume: bool = False) -> dict:
    """Run or extend a local experiment. One writer per output directory is supported."""
    if rounds < 1 or budget < 1 or keep < 1 or keep > budget or not 0 <= min_score <= 1:
        raise ValueError("require rounds >= 1, budget >= 1, 1 <= keep <= budget, and 0 <= min_score <= 1")
    input_path, output = Path(input_path), Path(output)
    adapter = load_adapter(adapter_spec)
    manifest = {"schema_version": 1, "engine_version": __version__, "engine_sha256": engine_hash(),
                "source_sha256": sha256_file(input_path), "adapter": adapter_identity(adapter, adapter_spec),
                "config": {"budget": budget, "keep": keep, "seed": seed, "min_score": min_score}}
    if resume:
        if read_json(output / "manifest.json") != manifest:
            raise ValueError("resume refused: input, config, adapter, or engine version changed")
    else:
        output.mkdir(parents=True, exist_ok=False)
        atomic_write(output / "manifest.json", json_text(manifest))
    previous_hash = (verify_commit(output / "seed", digest(manifest)) if (output / "seed").exists()
                     else prepare_seed(input_path, output, manifest))
    pool = read_records(output / "seed" / "records.jsonl")
    seed_report = read_json(output / "seed" / "report.json")
    feedback = Feedback.initial(seed_report["groups"])
    rounds_path = output / "rounds"
    rounds_path.mkdir(exist_ok=True)
    committed = sorted(path for path in rounds_path.iterdir() if not path.name.startswith("."))
    reports = []
    for index, path in enumerate(committed, 1):
        if path.name != f"{index:04d}" or not path.is_dir():
            raise ValueError("round checkpoints must be contiguous numbered directories")
        previous_hash = verify_commit(path, previous_hash)
        pool.extend(read_records(path / "selected.jsonl"))
        feedback = Feedback(**read_json(path / "feedback.json"))
        reports.append(read_json(path / "report.json"))
    if rounds < len(committed):
        raise ValueError("requested round count is below the already committed round count")
    for index in range(len(committed) + 1, rounds + 1):
        round_seed = int(hashlib.sha256(f"{seed}:{index}".encode()).hexdigest()[:16], 16)
        allocation = allocate(feedback.weights, budget)
        request = GenerationRequest(index, round_seed, allocation, tuple(pool), feedback)
        generated = SynthesisAgent().run(request, adapter)
        selected, decisions = EvaluationAgent().run(generated, pool, adapter, keep, min_score)
        feedback = FeedbackAgent().run(feedback, decisions, index)
        report = round_report(index, allocation, decisions, feedback, budget)
        previous_hash = commit_directory(rounds_path / f"{index:04d}", {
            "request.json": json_text(asdict(request)),
            "generated.jsonl": jsonl_text(asdict(record) for record in generated),
            "decisions.jsonl": jsonl_text(asdict(decision) for decision in decisions),
            "selected.jsonl": jsonl_text(asdict(record) for record in selected),
            "feedback.json": json_text(asdict(feedback)), "report.json": json_text(report),
            "messages.jsonl": jsonl_text([
                message("feedback", "synthesizer", "generation_request", "request.json"),
                message("synthesizer", "evaluator", "candidate_records", "generated.jsonl"),
                message("evaluator", "feedback", "admission_decisions", "decisions.jsonl"),
                message("feedback", "coordinator", "next_round_policy", "feedback.json"),
            ]),
        }, previous_hash)
        pool.extend(selected)
        reports.append(report)
    summary = {"mode": adapter.mode, "adapter": adapter.name, "source_sha256": manifest["source_sha256"],
               "seed": seed_report, "rounds": reports, "exported_records": len(pool),
               "last_commit_sha256": previous_hash,
               "metric_scope": "Deterministic rule compliance under the configured evaluator; no model training or benchmark claim."}
    atomic_write(output / "dataset.jsonl", jsonl_text(asdict(record) for record in pool))
    atomic_write(output / "summary.json", json_text(summary))
    atomic_write(output / "report.md", render_report(summary))
    return summary


def render_report(summary: dict) -> str:
    lines = ["# Datawheel quality report", "", f"Mode: **{summary['mode']}**; adapter: `{summary['adapter']}`.",
             "", summary["metric_scope"], "", f"Source SHA-256: `{summary['source_sha256']}`.", "",
             f"Import: {summary['seed']['input_records']} records; {summary['seed']['admitted']} admitted; "
             f"{summary['seed']['rejected']} rejected.",
             f"Cleaning/validation rejection reasons: `{summary['seed']['reasons']}`.", "",
             "| Round | Group | Allocated | Rule passes | Selected | Failures | Next allocation |",
             "| --- | --- | ---: | ---: | ---: | --- | ---: |"]
    for report in summary["rounds"]:
        for group, counts in report["groups"].items():
            lines.append(f"| {report['round']} | {group} | {counts['generated']} | {counts['passed']} | "
                         f"{counts['selected']} | {counts['failures']} | {report['next_allocation'][group]} |")
    lines.extend(["", f"Exported records: **{summary['exported_records']}** in `dataset.jsonl`.", "",
                  "Weights = 1 + 3 × cumulative rule-failure rate per group. Every group receives at least one "
                  "sample; remaining budget uses largest remainder, with alphabetical tie breaking.", "",
                  "`rounds/*/request.json` contains the feedback and examples actually given to generation. "
                  "`decisions.jsonl` records every judgement; `messages.jsonl` records role handoffs. "
                  "Passing but unselected records have reason `selection_limit`, and do not count as rule failures.", "",
                  "These are deterministic local agents. Offline fixture repairs are hand-written policy changes, "
                  "not evidence of LLM collaboration, learning, generalization, or production readiness.", ""])
    return "\n".join(lines)
