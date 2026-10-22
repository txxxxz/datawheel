"""An independent example domain, outside datawheel's core package."""

import re

from datawheel.contracts import Candidate, Record, Verdict, json_text


TOOLS = [
    {"name": "centimeters_to_meters", "parameters": {
        "type": "object", "properties": {"centimeters": {"type": "integer", "minimum": 0}},
        "required": ["centimeters"], "additionalProperties": False}},
    {"name": "minutes_to_seconds", "parameters": {
        "type": "object", "properties": {"minutes": {"type": "integer", "minimum": 0}},
        "required": ["minutes"], "additionalProperties": False}},
]


def expected_conversion(group: str, amount: int) -> tuple[str, dict, dict, str]:
    if group == "length":
        meters = f"{amount // 100}.{amount % 100:02d}"
        return "centimeters_to_meters", {"centimeters": amount}, {"meters": meters}, f"{meters} meters"
    return "minutes_to_seconds", {"minutes": amount}, {"seconds": amount * 60}, f"{amount * 60} seconds"


def make_candidate(group: str, amount: int, *, wrong: bool = False) -> Candidate:
    """Fixture authoring helper; the HTTP adapter does not import or call this."""
    unit, target = ("centimeters", "meters") if group == "length" else ("minutes", "seconds")
    prompt = f"Convert {amount} {unit} to {target}."
    tool, arguments, result, answer = expected_conversion(group, amount)
    if wrong:
        result = {"meters": "999.00"} if group == "length" else {"seconds": 999}
        answer = "999.00 meters" if group == "length" else "999 seconds"
    dialogue = [
        {"speaker": "user", "text": prompt},
        {"speaker": "assistant", "call": {"name": tool, "arguments": arguments}},
        {"speaker": "tool", "result": result},
        {"speaker": "assistant", "text": answer},
    ]
    return Candidate(group, prompt, answer, (f"seed-{group}",), {"dialogue": dialogue})


def evaluate(record: Record) -> Verdict:
    """Independently validate the user request, exact tool arguments/result and answer."""
    units = {"length": ("centimeters", "meters"), "duration": ("minutes", "seconds")}
    if record.group not in units:
        return Verdict(False, 0.0, "unknown_conversion")
    unit, target = units[record.group]
    match = re.fullmatch(rf"Convert ([0-9]{{1,9}}) {unit} to {target}\.", record.prompt)
    if not match:
        return Verdict(False, 0.0, "invalid_conversion_request")
    tool, arguments, result, answer = expected_conversion(record.group, int(match[1]))
    dialogue = record.metadata.get("dialogue")
    if (not isinstance(dialogue, list) or len(dialogue) != 4
            or any(not isinstance(turn, dict) for turn in dialogue)):
        return Verdict(False, 0.0, "invalid_dialogue")
    if dialogue[0] != {"speaker": "user", "text": record.prompt}:
        return Verdict(False, 0.0, "wrong_user_message")
    if json_text(dialogue[1]) != json_text({"speaker": "assistant", "call": {"name": tool, "arguments": arguments}}):
        return Verdict(False, 0.0, "wrong_tool_arguments")
    if json_text(dialogue[2]) != json_text({"speaker": "tool", "result": result}):
        return Verdict(False, 0.0, "wrong_conversion")
    if dialogue[3] != {"speaker": "assistant", "text": answer} or record.response != answer:
        return Verdict(False, 0.0, "wrong_final_answer")
    return Verdict(True, 1.0, "exact_conversion")
