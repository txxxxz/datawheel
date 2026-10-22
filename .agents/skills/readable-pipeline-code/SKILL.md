---
name: readable-pipeline-code
description: Implement or review Datawheel pipeline code with explicit data contracts, small modules, and behavioral tests. This guides coding agents; it is not a runtime pipeline plugin.
---

Start from the user-visible behavior and the records exchanged across roles. Identify the external boundary that owns validation, then keep internal code direct.

For a behavior change, write the smallest test that would fail without it. Test observable invariants: accepted data, rejection reasons, provenance, feedback-driven allocation, and resume equivalence. Avoid tests that merely mirror an implementation or match documentation wording.

Keep transformation, generation, evaluation, feedback, and persistence responsibilities legible. Prefer the existing contracts and ordinary functions to extra abstractions. A model adapter produces candidates; an independent evaluator decides what is acceptable.

Errors should explain the failed boundary and remain visible. Catch only a specific failure that the caller can meaningfully handle. Do not add broad exception handlers, silent fallback, repeated internal checks, automatic retries without a defined policy, or compatibility scaffolding for hypothetical users.

Before finishing, run the affected tests and one complete loop. If changing persistence, compare a resumed run with an uninterrupted run. If changing adapters, exercise an independent custom adapter. If changing installation, follow the README in a new environment outside the source directory.

Report measured outcomes and remaining limits. Offline fixtures demonstrate mechanics, not model intelligence or training gains.
