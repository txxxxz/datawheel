# Working on Datawheel

Keep the public API and the full import → clean → synthesize → evaluate/select → feedback loop easy to read. Read [.agents/skills/readable-pipeline-code/SKILL.md](.agents/skills/readable-pipeline-code/SKILL.md) when changing pipeline behavior.

- State the record, adapter, and persisted-artifact contracts before changing them.
- Add a failing behavioral test for a demonstrated bug or a new invariant, then make the smallest clear change.
- Validate external data and I/O boundaries. Inside the program, trust documented contracts.
- Let unexpected failures remain visible. Do not add broad catches, silent fallback, redundant validation, or speculative compatibility layers.
- Keep generation separate from deterministic evaluation. Never describe fixture pass rates as real model improvement.
- Preserve provenance, reproducibility, and the connection between feedback and the next round.
- Use newly authored synthetic fixtures. Do not commit credentials, private source material, raw customer data, or run outputs.
- Run the documented tests and a clean installation when changing packaging or the quickstart.

Prefer a small function or data class to a new framework, registry, service, or dependency. Add complexity only for an observed requirement.
