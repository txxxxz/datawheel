"""A complete small adapter you can replace with your own data/model code.

This example still runs offline. A real generator belongs in generate(); keep
evaluate() independent and deterministic. Version all model/config dependencies.
"""

import random

from datawheel.contracts import Candidate, GenerationRequest, Record, Verdict


class UppercaseAdapter:
    name = "custom-uppercase-example"
    version = "1"
    mode = "offline-demo"

    def generate(self, request: GenerationRequest) -> list[Candidate]:
        rng = random.Random(request.seed)
        parent = request.examples[0]
        return [Candidate("uppercase", f"Uppercase: sample-{number}", f"SAMPLE-{number}", (parent.id,))
                for number in (rng.randrange(1000000000) for _ in range(request.allocation["uppercase"]))]

    def evaluate(self, record: Record) -> Verdict:
        valid = (record.group == "uppercase" and record.prompt.startswith("Uppercase: ")
                 and record.response == record.prompt.removeprefix("Uppercase: ").upper())
        return Verdict(valid, float(valid), "correct_uppercase" if valid else "incorrect_uppercase")
