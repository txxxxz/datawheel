# Configured model roles over HTTP

This example exercises the real HTTP adapter with a new unit-conversion domain. The domain, tool descriptions, independent evaluator, seeds and hand-authored prerecorded responses all live in this directory. Nothing in the core package imports this domain.

After installing Datawheel, run from the repository root:

```sh
python examples/model_http/replay.py --output runs/http-replay
datawheel report runs/http-replay
```

`replay.py` starts a temporary server bound to `127.0.0.1`, substitutes its explicit endpoint into the example config, and runs two rounds with a budget of six. It sends six actual HTTP POSTs and exports 12 records. The responses are fixtures written for this project; they were not obtained from a real model. A mistaken critic returns no issues in round 1, yet the independent evaluator rejects two wrong conversions. Round 2 receives those failures and an allocation of four length / two duration examples. Its prerecorded answers are valid. This tests the connection and control flow, not learned repair or real-model efficacy.

## Minimal configuration

Copy [config.json](config.json) and set these fields for your service:

| Field | Contract |
| --- | --- |
| `name`, `version` | Nonempty identity strings; version all relevant model/helper changes |
| `mode` | `http-replay` for fixtures or `http-model` for your model service |
| `endpoint` | Full explicit HTTP(S) chat-completions URL; no username, password, query or fragment |
| `generator` | `model` and `system_prompt` strings used for draft and revision |
| `critic` | Its own `model` and `system_prompt` strings, used in a separate review call |
| `evaluator` | `callable: "module:function"` and `version`; function accepts `Record` and returns `Verdict` |
| `domain` | A JSON object with your task description, tool schemas and constraints |
| `temperature` | Optional number in [0, 2], default 0 |
| `timeout_seconds` | Optional positive finite number, default 30 per HTTP request |

Unknown configuration fields are rejected. There are no credential, API-key, custom-header or environment-variable inputs, no default endpoint, no redirects, no automatic retries and no inherited HTTP proxy. This supports an unauthenticated/self-hosted service or a gateway whose authentication you manage separately. Configure both roles at that endpoint; they may use different models.

The configuration is saved in full and hashed in the manifest. Keep it free of secrets. Requests include the full accepted example pool, domain configuration, feedback and draft/review content. Their bodies and raw UTF-8 response bodies are saved locally; there is no redaction or privacy filter.

## Exact wire contract

Each request is a nonstreaming JSON POST with only `model`, `messages`, `temperature`, and `stream: false`. `messages` has a system instruction followed by a user message containing JSON with:

- `stage`: `draft`, `critique` or `revise`;
- `generation_request`: the round, seed, allocation, accepted examples and previous feedback;
- `domain`: your JSON task/tool descriptions;
- `output_contract`: the expected structured output shape;
- `draft` for critique/revision, and `critique` for revision.

The endpoint must return exactly one `choices` entry with `finish_reason: "stop"` and `message.role: "assistant"`. `message.content` must be a string containing a JSON object, without Markdown fences. Draft and revision return:

```json
{"candidates":[{"group":"length","prompt":"...","response":"...","parent_ids":["seed-length"],"metadata":{"dialogue":[]}}]}
```

The critic returns:

```json
{"issues":["Explain a specific problem or repair instruction."]}
```

Final candidates must match the requested group counts and reference existing example IDs. Critic output is supplied to revision but never used as an admission decision. The configured deterministic evaluator checks final records; ordinary score/threshold/deduplication/selection rules still apply.

This intentionally supports one text-output chat-completions contract. Streaming, provider tool-call responses, provider SDKs and automatic repair of malformed JSON are unsupported. `domain.tools` is context for producing data, not a request to execute a real tool. HTTP failures, truncated responses, invalid JSON or final contract failures stop the round visibly; the implementation never substitutes the draft for a failed revision.

## Bring a new domain

Write a standalone evaluator as shown in [conversion.py](conversion.py), supply your own JSONL records, and change `domain` and the evaluator entry point in the config. No core edits are necessary:

```sh
PYTHONPATH=/path/to/your/evaluator datawheel run \
  --input /path/to/your/records.jsonl --output runs/your-domain \
  --adapter datawheel.chat_adapter:ChatAdapter \
  --adapter-config /path/to/your/config.json
```

Your evaluator owns schema, user-intent and world-state checks. In this example it recomputes centimeter-to-meter and minute-to-second conversions and validates the dialogue's arguments, results and final answer. Its comparison distinguishes JSON booleans from integers. A different domain can use a different metadata/conversation structure.

Adapter and evaluator source files, evaluator version and the full config hash participate in resume identity. Imported helper changes or server-side model changes require a version change. Already committed rounds issue no model calls on resume. An uncommitted round restarts from draft, so remote calls can repeat. Handled generation failures retain request/call evidence under `failed/`; hard process termination or a later evaluator/programming failure can lose uncommitted trace data. There is no per-call durability or exactly-once guarantee.

Before reporting real-model effectiveness, supply and version an actual endpoint/model, your generation/review prompts, an independently checked evaluator, representative source data and a held-out evaluation set. Run measured comparisons under a fixed budget and report both quality and cost. This repository's replay results do not supply that evidence. Separate generator/critic requests, even with different prompts, are not proof of independent judgement or improved quality.
