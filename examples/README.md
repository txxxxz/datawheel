# Public, synthetic examples

All records in this directory were written for this project. No customer conversations or private project data are included. The default adapters run offline; [the HTTP example](model_http/README.md) exercises the configurable model adapter against hand-authored responses served on loopback.

## Tool conversations: the main example

`tool_dialogues.jsonl` contains fictional inventory queries and support ticket-status queries. Run it from the repository root:

```sh
datawheel run --input examples/tool_dialogues.jsonl --output runs/dialogue
datawheel report runs/dialogue
```

The record's `prompt` is the user request and `response` is the final assistant answer. `metadata.tools` contains the advertised function schema. `metadata.messages` contains four turns: user request, assistant tool call, tool result and assistant answer. Tool arguments and results are JSON objects in this project's interchange format; this is not a provider-specific chat API wire format.

Two read-only simulated tools are defined in [tool_dialogue.py](../src/datawheel/tool_dialogue.py):

| Group | Request template | Tool and arguments | Public fixture truth |
| --- | --- | --- | --- |
| `inventory` | `Check stock for SKU-101 at north.` | `get_stock(sku, warehouse)` | `(sku_number × 7 + warehouse_offset) % 101`; offsets: north 11, south 37 |
| `ticket_status` | `Check status for ticket T-202.` | `get_ticket(ticket_id)` | Number modulo 3 selects `open`, `pending`, or `resolved` |

Identifiers use ASCII digits. The evaluator parses the documented request template and independently recomputes the tool result from these rules. It checks the tool schema, conversation roles, user content, function name, exact arguments, tool-call linkage, result and final answer. A self-consistent conversation using a different item from the user's request fails. It does not assess unrestricted language intent or a live backend.

The 10 input records demonstrate:

| Input | Outcome |
| --- | --- |
| Two valid conversations | Admitted |
| One valid conversation with outer whitespace | Normalized and admitted |
| One repeated conversation | `duplicate` |
| One empty answer | `empty_text` |
| One changed tool schema | `tool_schema_mismatch` |
| One wrong argument | `tool_arguments_mismatch` |
| One wrong result | `tool_result_mismatch` |
| One wrong final answer | `final_answer_mismatch` |
| One broken tool-call reference | `tool_call_id_mismatch` |

Generation starts with equal group budgets. The baseline generator intentionally corrupts every second inventory tool result. The evaluator rejects these even though the generator's final answer agrees with its own incorrect result. Feedback counts the failures, increases inventory's next budget from 6 to 8, and sends the reason to the generator. Seeing that reason enables the hand-written `feedback:verify_tool_result` strategy. Round 2 recomputes consistent results and passes all 12 candidates. This is an explicit offline policy demonstration, not a trained-model result.

Inspect `rounds/0001/decisions.jsonl` for the failures, `rounds/0001/feedback.json` for their aggregation, and `rounds/0002/request.json` for their delivery. Generated metadata records which fixture strategy ran.

## Arithmetic: a minimal diagnostic

```sh
datawheel run --input examples/arithmetic.jsonl --output runs/arithmetic \
  --adapter datawheel.adapters:ArithmeticAdapter
```

Exact integer arithmetic makes scheduling and recovery easy to inspect. Multiplication has a controlled error pattern, so round 2 allocates 8 multiplication and 4 addition samples. The generator does not repair that pattern; this demonstrates budget adaptation separately from the dialogue fixture's repair strategy.

## Custom adapter: a small integration example

```sh
PYTHONPATH=examples datawheel run --input examples/uppercase.jsonl --output runs/custom \
  --adapter custom_adapter:UppercaseAdapter
```

[custom_adapter.py](custom_adapter.py) shows the complete `generate`/`evaluate` boundary in a few lines. Its independent validator checks exact uppercase conversion. Copy the file, replace the generation code and task validator, change the adapter identity/version/mode, and supply your own JSONL records. The explicit `PYTHONPATH` makes the adapter importable when using the installed console command; installing your adapter as a package also works.
