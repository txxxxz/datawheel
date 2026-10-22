from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from examples.model_http.replay import fixture_server
from examples.model_http.conversion import evaluate, make_candidate
from datawheel.contracts import Record
from datawheel.pipeline import run
from datawheel.store import read_json, read_records


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/model_http"
ADAPTER = "datawheel.chat_adapter:ChatAdapter"


class ChatAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = read_json(EXAMPLE / "config.json")
        self.config["evaluator"]["callable"] = "examples.model_http.conversion:evaluate"
        self.recordings = read_json(EXAMPLE / "responses.json")

    def config_file(self, endpoint):
        self.config["endpoint"] = endpoint
        path = self.root / "config.json"
        path.write_text(json.dumps(self.config))
        return path

    def run_model(self, config, output="run", **kwargs):
        return run(EXAMPLE / "seeds.jsonl", self.root / output, budget=6, keep=6,
                   adapter_spec=ADAPTER, adapter_config=config, **kwargs)

    def test_three_model_calls_feedback_and_independent_admission(self):
        with fixture_server(self.recordings) as (endpoint, calls):
            config = self.config_file(endpoint)
            summary = self.run_model(config)
        self.assertEqual(len(calls), 6)
        self.assertEqual([call["body"]["model"] for call in calls],
                         ["recorded-generator", "recorded-critic", "recorded-generator"] * 2)
        contexts = [json.loads(call["body"]["messages"][1]["content"]) for call in calls]
        self.assertEqual([context["stage"] for context in contexts], ["draft", "critique", "revise"] * 2)
        self.assertEqual(contexts[2]["draft"], contexts[1]["draft"])
        self.assertEqual(contexts[2]["critique"]["issues"], [])  # A mistaken critic has no admission authority.
        self.assertEqual(summary["rounds"][0]["groups"]["length"]["failures"], {"wrong_conversion": 2})
        for context in contexts[3:]:
            self.assertEqual(context["generation_request"]["feedback"]["reasons"]["length"], {"wrong_conversion": 2})
            self.assertEqual(context["generation_request"]["allocation"], {"duration": 2, "length": 4})
            self.assertEqual(context["domain"]["tools"], self.config["domain"]["tools"])
        self.assertEqual(summary["rounds"][1]["passed"], 6)
        self.assertTrue(all("Authorization" not in call["headers"] for call in calls))
        trace = [json.loads(line) for line in (self.root / "run/rounds/0001/model_calls.jsonl").read_text().splitlines()]
        self.assertEqual([item["role"] for item in trace], ["generator", "critic", "generator"])
        self.assertEqual(trace[0]["request"], calls[0]["body"])
        self.assertEqual(json.loads(trace[0]["response_body"]), self.recordings[0]["response"])

    def test_invalid_final_response_has_trace_and_never_falls_back_to_draft(self):
        recordings = deepcopy(self.recordings)
        recordings[2]["response"]["choices"][0]["message"]["content"] = "not JSON"
        with fixture_server(recordings) as (endpoint, calls):
            with self.assertRaisesRegex(ValueError, "revise"):
                self.run_model(self.config_file(endpoint))
        self.assertEqual(len(calls), 3)
        self.assertFalse((self.root / "run/rounds/0001").exists())
        failures = list((self.root / "run/failed").glob("*/model_calls.jsonl"))
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(failures[0].read_text().splitlines()), 3)
        self.assertFalse((self.root / "run/dataset.jsonl").exists())

    def test_http_error_and_truncation_are_not_retried(self):
        for case in ("http", "truncated"):
            with self.subTest(case=case):
                recordings = deepcopy(self.recordings)
                if case == "http":
                    recordings[0].update(status=503, raw_body='{"error":"fixture unavailable"}')
                else:
                    recordings[0]["response"]["choices"][0]["finish_reason"] = "length"
                with fixture_server(recordings) as (endpoint, calls):
                    with self.assertRaises(ValueError):
                        self.run_model(self.config_file(endpoint), output=case)
                self.assertEqual(len(calls), 1)
                self.assertFalse((self.root / case / "rounds/0001").exists())

    def test_resume_sends_no_calls_and_refuses_config_or_evaluator_change(self):
        with fixture_server(self.recordings) as (endpoint, calls):
            config = self.config_file(endpoint)
            self.run_model(config)
            self.run_model(config, resume=True)
            self.assertEqual(len(calls), 6)
            original = deepcopy(self.config)
            mutations = [
                lambda value: value["generator"].update(model="different-model"),
                lambda value: value["critic"].update(system_prompt="different review policy"),
                lambda value: value["domain"].update(description="different domain"),
                lambda value: value["evaluator"].update(version="2"),
            ]
            for mutate in mutations:
                self.config = deepcopy(original)
                mutate(self.config)
                with self.assertRaisesRegex(ValueError, "resume refused"):
                    self.run_model(self.config_file(endpoint), resume=True)
            self.assertEqual(len(calls), 6)
        manifest = read_json(self.root / "run/manifest.json")
        self.assertIn("implementation_sha256", manifest["adapter"]["dependencies"]["evaluator"])
        self.assertEqual(manifest["adapter_config"], original)

    def test_endpoint_and_credentials_are_explicit(self):
        from datawheel.chat_adapter import ChatAdapter
        bad_configs = []
        missing = deepcopy(self.config)
        del missing["endpoint"]
        bad_configs.append(missing)
        for endpoint in ("http://user:secret@127.0.0.1/v1/chat/completions",
                         "http://127.0.0.1/v1/chat/completions?api_key=secret"):
            value = deepcopy(self.config)
            value["endpoint"] = endpoint
            bad_configs.append(value)
        credentials = deepcopy(self.config)
        credentials["api_key_env"] = "DO_NOT_READ_THIS"
        bad_configs.append(credentials)
        for config in bad_configs:
            with self.subTest(config_keys=list(config)):
                with self.assertRaises(ValueError):
                    ChatAdapter(config)

    def test_conversion_evaluator_rejects_booleans_in_integer_positions(self):
        candidate = make_candidate("duration", 1)
        candidate.metadata["dialogue"][1]["call"]["arguments"]["minutes"] = True
        record = Record("bad-argument", candidate.group, candidate.prompt, candidate.response, candidate.metadata)
        self.assertEqual(evaluate(record).reason, "wrong_tool_arguments")
        candidate = make_candidate("duration", 0)
        candidate.metadata["dialogue"][2]["result"]["seconds"] = False
        record = Record("bad-result", candidate.group, candidate.prompt, candidate.response, candidate.metadata)
        self.assertEqual(evaluate(record).reason, "wrong_conversion")

    def test_final_candidate_contract_failure_keeps_all_calls(self):
        recordings = deepcopy(self.recordings)
        final = recordings[2]["response"]["choices"][0]["message"]
        value = json.loads(final["content"])
        value["candidates"][0]["parent_ids"] = ["unknown-parent"]
        final["content"] = json.dumps(value)
        with fixture_server(recordings) as (endpoint, calls):
            with self.assertRaisesRegex(ValueError, "parent_id"):
                self.run_model(self.config_file(endpoint))
        self.assertEqual(len(calls), 3)
        failure = next((self.root / "run/failed").glob("*/model_calls.jsonl"))
        self.assertEqual(len(failure.read_text().splitlines()), 3)
        self.assertFalse((self.root / "run/rounds/0001").exists())


if __name__ == "__main__":
    unittest.main()
