from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from datawheel.adapters import ArithmeticAdapter
from datawheel.agents import CleanAgent, EvaluationAgent, SynthesisAgent
from datawheel.contracts import Candidate, Feedback, GenerationRequest, Record, digest
from datawheel.pipeline import run
from datawheel.store import read_json, read_records
from datawheel.tool_dialogue import ToolDialogueAdapter, evaluate_dialogue, make_dialogue


ROOT = Path(__file__).resolve().parents[1]
DIALOGUES = ROOT / "examples/tool_dialogues.jsonl"
ARITHMETIC = ROOT / "examples/arithmetic.jsonl"


def tree_bytes(root: Path) -> dict:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_feedback_changes_next_round_budget_and_generation_strategy(self):
        original = DIALOGUES.read_bytes()
        output = self.root / "dialogue"
        summary = run(DIALOGUES, output)
        first, second = summary["rounds"]
        self.assertEqual(first["allocation"], {"inventory": 6, "ticket_status": 6})
        self.assertEqual(first["groups"]["inventory"]["failures"], {"tool_result_mismatch": 3})
        self.assertEqual(second["allocation"], {"inventory": 8, "ticket_status": 4})
        self.assertEqual(second["groups"]["inventory"]["failures"], {})
        request = read_json(output / "rounds/0002/request.json")
        self.assertEqual(request["feedback"]["round_index"], 1)
        self.assertEqual(request["feedback"]["reasons"]["inventory"]["tool_result_mismatch"], 3)
        generated = read_records(output / "rounds/0002/generated.jsonl")
        inventory = [record for record in generated if record.group == "inventory"]
        self.assertEqual(len(inventory), 8)
        self.assertTrue(all(record.metadata["strategy"] == "feedback:verify_tool_result" for record in inventory))
        self.assertEqual(DIALOGUES.read_bytes(), original)
        self.assertGreater(summary["seed"]["rejected"], 0)

    def test_feedback_is_causal_with_seed_and_budget_held_constant(self):
        seeds = tuple(record for record in read_records(DIALOGUES) if evaluate_dialogue(record).passed)
        feedback = Feedback.initial(["inventory", "ticket_status"])
        request = GenerationRequest(1, 7, {"inventory": 4, "ticket_status": 4}, seeds, feedback)
        baseline, _ = SynthesisAgent().run(request, ToolDialogueAdapter())
        repaired_feedback = replace(feedback, reasons={"inventory": {"tool_result_mismatch": 2}, "ticket_status": {}})
        repaired, _ = SynthesisAgent().run(replace(request, feedback=repaired_feedback), ToolDialogueAdapter())
        self.assertEqual([record.prompt for record in baseline], [record.prompt for record in repaired])
        self.assertEqual(sum(evaluate_dialogue(record).passed for record in baseline), 6)
        self.assertEqual(sum(evaluate_dialogue(record).passed for record in repaired), 8)

    def test_arithmetic_loop_changes_actual_allocation(self):
        summary = run(ARITHMETIC, self.root / "math", adapter_spec="datawheel.adapters:ArithmeticAdapter")
        self.assertEqual(summary["rounds"][0]["allocation"], {"addition": 6, "multiplication": 6})
        self.assertEqual(summary["rounds"][1]["allocation"], {"addition": 4, "multiplication": 8})
        self.assertEqual(summary["seed"]["reasons"], {"duplicate": 1, "empty_text": 1, "wrong_answer": 1})

    def test_resume_and_repeat_are_byte_identical(self):
        direct, resumed, repeat = (self.root / name for name in ("direct", "resumed", "repeat"))
        run(DIALOGUES, direct)
        run(DIALOGUES, resumed, rounds=1)
        run(DIALOGUES, resumed, rounds=2, resume=True)
        run(DIALOGUES, repeat)
        self.assertEqual(tree_bytes(direct), tree_bytes(resumed))
        self.assertEqual(tree_bytes(direct), tree_bytes(repeat))

    def test_interruption_keeps_committed_round_and_resumes(self):
        interrupted, direct = self.root / "interrupted", self.root / "direct"
        generate = SynthesisAgent.run

        def fail_second(agent, request, adapter):
            if request.round_index == 2:
                raise RuntimeError("simulated generator interruption")
            return generate(agent, request, adapter)

        with patch.object(SynthesisAgent, "run", fail_second):
            with self.assertRaisesRegex(RuntimeError, "simulated generator interruption"):
                run(DIALOGUES, interrupted)
        self.assertTrue((interrupted / "rounds/0001/commit.json").exists())
        self.assertFalse((interrupted / "rounds/0002").exists())
        run(DIALOGUES, interrupted, resume=True)
        run(DIALOGUES, direct)
        self.assertEqual(tree_bytes(interrupted), tree_bytes(direct))

    def test_commit_survives_interruption_before_export(self):
        from datawheel.store import atomic_write
        output = self.root / "before-export"

        def fail_export(path, text):
            if path.name == "dataset.jsonl":
                raise OSError("simulated export interruption")
            atomic_write(path, text)

        with patch("datawheel.pipeline.atomic_write", fail_export):
            with self.assertRaisesRegex(OSError, "export interruption"):
                run(DIALOGUES, output)
        with patch.object(SynthesisAgent, "run", side_effect=AssertionError("must not regenerate committed rounds")):
            summary = run(DIALOGUES, output, resume=True)
        self.assertEqual(len(read_records(output / "dataset.jsonl")), summary["exported_records"])

    def test_resume_refuses_changed_source_config_or_checkpoint(self):
        source = self.root / "source.jsonl"
        source.write_bytes(DIALOGUES.read_bytes())
        output = self.root / "output"
        run(source, output, rounds=1)
        with self.assertRaisesRegex(ValueError, "resume refused"):
            run(source, output, resume=True, seed=8)
        source.write_text(source.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "resume refused"):
            run(source, output, resume=True)
        source.write_bytes(DIALOGUES.read_bytes())
        checkpoint = output / "rounds/0001/generated.jsonl"
        checkpoint.write_text(checkpoint.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "checkpoint content changed"):
            run(source, output, resume=True)

    def test_every_exported_synthetic_record_has_lineage_and_passes(self):
        output = self.root / "lineage"
        run(DIALOGUES, output)
        records = read_records(output / "dataset.jsonl")
        known_ids = set()
        for record in records:
            self.assertTrue(evaluate_dialogue(record).passed)
            if record.provenance["kind"] == "synthetic":
                self.assertTrue(record.provenance["parent_ids"])
                self.assertLessEqual(set(record.provenance["parent_ids"]), known_ids)
                self.assertEqual(record.provenance["mode"], "offline-mock")
            else:
                self.assertIn("source_sha256", record.provenance)
            known_ids.add(record.id)

    def test_custom_adapter_is_replaceable_without_pipeline_edits(self):
        summary = run(ROOT / "examples/uppercase.jsonl", self.root / "custom",
                      adapter_spec="examples.custom_adapter:UppercaseAdapter")
        self.assertEqual(summary["adapter"], "custom-uppercase-example")
        self.assertEqual(summary["seed"]["reasons"], {"incorrect_uppercase": 1})
        self.assertTrue(all(report["passed"] == 12 for report in summary["rounds"]))
        self.assertNotIn("synthetic fixtures", summary["metric_scope"])

    def test_invalid_import_reports_line_and_does_not_replace_existing_run(self):
        source = self.root / "bad.jsonl"
        source.write_text('{"id": "bad", "group": "test", "prompt": 42, "response": "x"}\n')
        with self.assertRaisesRegex(ValueError, "bad.jsonl:1: prompt must be a string"):
            run(source, self.root / "bad")
        output = self.root / "existing"
        run(DIALOGUES, output, rounds=1)
        before = tree_bytes(output)
        with self.assertRaises(FileExistsError):
            run(DIALOGUES, output)
        self.assertEqual(tree_bytes(output), before)


class RoleTests(unittest.TestCase):
    def test_cleaning_preserves_internal_whitespace_and_tracks_changes(self):
        first = Record("a", "text", "  x\n  y  ", " e\u0301 ")
        duplicate = Record("b", "text", "x\n  y", "é")
        cleaned, rejected, changed = CleanAgent().run([first, duplicate])
        self.assertEqual(cleaned[0].prompt, "x\n  y")
        self.assertEqual(cleaned[0].response, "é")
        self.assertEqual(changed, ["a"])
        self.assertEqual([decision.reason for decision in rejected], ["duplicate"])

    def test_selection_is_stable_and_quota_is_not_a_rule_failure(self):
        records = [Record("b", "addition", "1 + 2", "3"), Record("a", "addition", "1 + 1", "2")]
        selected, decisions = EvaluationAgent().run(records, [], ArithmeticAdapter(), keep=1, min_score=1)
        self.assertEqual([record.id for record in selected], ["a"])
        self.assertTrue(all(decision.passed for decision in decisions))
        self.assertEqual(decisions[0].reason, "selection_limit")

    def test_generator_must_supply_a_known_parent(self):
        class NoParentAdapter(ArithmeticAdapter):
            def generate(self, request):
                return [Candidate("addition", "1 + 1", "2")]

        parent = Record("parent", "addition", "2 + 3", "5")
        request = GenerationRequest(1, 7, {"addition": 1}, (parent,), Feedback.initial(["addition"]))
        with self.assertRaisesRegex(ValueError, "parent"):
            SynthesisAgent().run(request, NoParentAdapter())

    def test_generated_id_collision_is_rejected_at_adapter_boundary(self):
        candidate = Candidate("addition", "1 + 1", "2", ("parent",))

        class CollisionAdapter(ArithmeticAdapter):
            def generate(self, request):
                return [candidate]

        collision_id = f"r1-0-{digest(asdict(candidate))[:12]}"
        seeds = (Record("parent", "addition", "2 + 3", "5"),
                 Record(collision_id, "addition", "3 + 4", "7"))
        request = GenerationRequest(1, 7, {"addition": 1}, seeds, Feedback.initial(["addition"]))
        with self.assertRaisesRegex(ValueError, "id collision"):
            SynthesisAgent().run(request, CollisionAdapter())

    def test_tool_validator_rejects_each_inconsistency(self):
        candidate = make_dialogue("inventory", 104)
        good = Record("good", candidate.group, candidate.prompt, candidate.response, candidate.metadata)
        self.assertTrue(evaluate_dialogue(good).passed)
        mutations = [
            ("tool_schema_mismatch", lambda data: data["tools"][0]["function"].update(name="other_tool")),
            ("tool_name_mismatch", lambda data: data["messages"][1]["tool_calls"][0]["function"].update(name="other_tool")),
            ("tool_arguments_mismatch", lambda data: data["messages"][1]["tool_calls"][0]["function"]["arguments"].update(sku="SKU-999")),
            ("tool_call_id_mismatch", lambda data: data["messages"][2].update(tool_call_id="wrong")),
            ("tool_result_mismatch", lambda data: data["messages"][2]["content"].update(available=999)),
            ("final_answer_mismatch", lambda data: data["messages"][3].update(content="Unknown.")),
        ]
        for reason, mutate in mutations:
            with self.subTest(reason=reason):
                metadata = deepcopy(good.metadata)
                mutate(metadata)
                self.assertEqual(evaluate_dialogue(replace(good, metadata=metadata)).reason, reason)

    def test_correct_tool_result_for_wrong_user_request_is_rejected(self):
        candidate = make_dialogue("inventory", 999)
        wrong_request = "Check stock for SKU-104 at north."
        metadata = deepcopy(candidate.metadata)
        metadata["messages"][0]["content"] = wrong_request
        record = Record("mismatch", "inventory", wrong_request, candidate.response, metadata)
        self.assertEqual(evaluate_dialogue(record).reason, "tool_arguments_mismatch")

    def test_tool_identifiers_obey_ascii_schema(self):
        for group in ("inventory", "ticket_status"):
            with self.subTest(group=group):
                candidate = make_dialogue(group, "١٢")
                record = Record("unicode", group, candidate.prompt, candidate.response, candidate.metadata)
                self.assertEqual(evaluate_dialogue(record).reason, "invalid_request")


if __name__ == "__main__":
    unittest.main()
