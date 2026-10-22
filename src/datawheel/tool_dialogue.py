"""Fictional read-only tools and exact dialogue validation, entirely offline.

The generator's fault injection and feedback repair are hand-written fixtures.
They demonstrate a control loop, not model learning or real tool execution.
"""

import random
import re

from .contracts import Candidate, GenerationRequest, Record, Verdict, json_text


TOOL_SCHEMAS = {
    "inventory": {"type": "function", "function": {
        "name": "get_stock", "description": "Query fictional warehouse stock.",
        "parameters": {"type": "object", "properties": {
            "sku": {"type": "string", "pattern": "^SKU-[0-9]+$"},
            "warehouse": {"type": "string", "enum": ["north", "south"]}},
            "required": ["sku", "warehouse"], "additionalProperties": False}}},
    "ticket_status": {"type": "function", "function": {
        "name": "get_ticket", "description": "Query a fictional support ticket.",
        "parameters": {"type": "object", "properties": {
            "ticket_id": {"type": "string", "pattern": "^T-[0-9]+$"}},
            "required": ["ticket_id"], "additionalProperties": False}}},
}


def simulate_tool(name: str, arguments: dict) -> dict:
    """Public fixture world; the validator recomputes this, never trusts claimed truth."""
    if name == "get_stock":
        number = int(arguments["sku"].removeprefix("SKU-"))
        offset = 11 if arguments["warehouse"] == "north" else 37
        return {**arguments, "available": (number * 7 + offset) % 101}
    if name == "get_ticket":
        number = int(arguments["ticket_id"].removeprefix("T-"))
        return {**arguments, "status": ("open", "pending", "resolved")[number % 3]}
    raise ValueError(f"unsupported fictional tool: {name}")


def final_answer(name: str, result: dict) -> str:
    if name == "get_stock":
        return f"{result['sku']} has {result['available']} units at {result['warehouse']}."
    return f"Ticket {result['ticket_id']} is {result['status']}."


def make_dialogue(group: str, number: int, warehouse: str = "north", *,
                  corrupt_result: bool = False, strategy: str = "baseline") -> Candidate:
    """Build a synthetic conversation; also used to construct the public input fixtures."""
    if group == "inventory":
        arguments = {"sku": f"SKU-{number}", "warehouse": warehouse}
        prompt = f"Check stock for SKU-{number} at {warehouse}."
    elif group == "ticket_status":
        arguments = {"ticket_id": f"T-{number}"}
        prompt = f"Check status for ticket T-{number}."
    else:
        raise ValueError(f"unsupported dialogue group: {group}")
    name = TOOL_SCHEMAS[group]["function"]["name"]
    result = simulate_tool(name, arguments)
    if corrupt_result:
        if group == "inventory":
            result["available"] += 1
        else:
            result["status"] = "unknown"
    answer = final_answer(name, result)
    messages = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "tool_calls": [{"id": "call-1", "type": "function",
            "function": {"name": name, "arguments": arguments}}]},
        {"role": "tool", "tool_call_id": "call-1", "content": result},
        {"role": "assistant", "content": answer},
    ]
    return Candidate(group, prompt, answer, metadata={"tools": [TOOL_SCHEMAS[group]],
                                                     "messages": messages, "strategy": strategy})


def evaluate_dialogue(record: Record) -> Verdict:
    """Validate schema, intent, linkage, world-state result, and final answer separately."""
    def reject(reason: str) -> Verdict:
        return Verdict(False, 0.0, reason)

    if record.group not in TOOL_SCHEMAS:
        return reject("unsupported_group")
    if record.metadata.get("tools") != [TOOL_SCHEMAS[record.group]]:
        return reject("tool_schema_mismatch")
    if record.group == "inventory":
        match = re.fullmatch(r"Check stock for (SKU-[0-9]+) at (north|south)\.", record.prompt)
        if not match:
            return reject("invalid_request")
        arguments = {"sku": match[1], "warehouse": match[2]}
    else:
        match = re.fullmatch(r"Check status for ticket (T-[0-9]+)\.", record.prompt)
        if not match:
            return reject("invalid_request")
        arguments = {"ticket_id": match[1]}
    messages = record.metadata.get("messages")
    if (not isinstance(messages, list) or len(messages) != 4
            or any(not isinstance(message, dict) for message in messages)
            or [message.get("role") for message in messages] != ["user", "assistant", "tool", "assistant"]):
        return reject("invalid_conversation")
    if messages[0].get("content") != record.prompt:
        return reject("user_message_mismatch")
    calls = messages[1].get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict):
        return reject("invalid_tool_call")
    call = calls[0]
    function = call.get("function")
    if (call.get("type") != "function" or not isinstance(call.get("id"), str) or not call["id"]
            or not isinstance(function, dict)):
        return reject("invalid_tool_call")
    name = TOOL_SCHEMAS[record.group]["function"]["name"]
    if function.get("name") != name:
        return reject("tool_name_mismatch")
    if function.get("arguments") != arguments:
        return reject("tool_arguments_mismatch")
    if messages[2].get("tool_call_id") != call["id"]:
        return reject("tool_call_id_mismatch")
    expected = simulate_tool(name, arguments)
    if json_text(messages[2].get("content")) != json_text(expected):
        return reject("tool_result_mismatch")
    answer = final_answer(name, expected)
    if record.response != answer or messages[3].get("content") != answer:
        return reject("final_answer_mismatch")
    return Verdict(True, 1.0, "consistent_tool_dialogue")


class ToolDialogueAdapter:
    name = "fictional-tool-dialogue"
    version = "1"
    mode = "offline-mock"

    evaluate = staticmethod(evaluate_dialogue)

    def generate(self, request: GenerationRequest) -> list[Candidate]:
        rng = random.Random(request.seed)
        candidates = []
        for group, count in request.allocation.items():
            parents = [record for record in request.examples if record.group == group]
            repair = request.feedback.reasons[group].get("tool_result_mismatch", 0) > 0
            for index in range(count):
                candidate = make_dialogue(
                    group, rng.randrange(100, 1000000000), rng.choice(["north", "south"]),
                    corrupt_result=group == "inventory" and index % 2 == 0 and not repair,
                    strategy="feedback:verify_tool_result" if repair else "baseline",
                )
                candidates.append(Candidate(candidate.group, candidate.prompt, candidate.response,
                                            (rng.choice(parents).id,), candidate.metadata))
        return candidates
