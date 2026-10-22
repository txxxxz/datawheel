# Goal: a reusable data flywheel

A developer who has never seen this project can install it in a fresh Python environment and run import → clean → synthesize → evaluate/select → feedback → next round. They can replace the data and model using a small Python adapter, without a cloud account or an orchestration framework.

This is the repository's goal document. No platform goal has been created.

## Acceptance criteria

1. The README quickstart works from a clean checkout and a fresh environment.
2. Import and cleaning retain source lineage, explain rejected records, and leave the input unchanged.
3. Generation and evaluation are separate. Bundled generators are explicitly offline/mock, and their synthetic outputs are evaluated by exact, deterministic rules. Include a public synthetic dialogue/tool-call example with tool schema, argument, result, and answer consistency checks; arithmetic alone is insufficient.
4. First-round feedback demonstrably changes second-round sampling or synthesis. The report shows the policy, evidence, and before/after allocation. In the dialogue example, show concrete cleaning and rejection reasons and how failed verification changes the next generation request or strategy.
5. Persisted artifacts identify input content, configuration, adapter versions, and parent rounds. Every accepted synthetic record has source lineage.
6. Re-running the same input/configuration is reproducible. Interrupted and resumed work is equivalent to an uninterrupted run at the supported checkpoint boundary.
7. Changed sources or incompatible configuration cannot silently resume an old run.
8. A small independent adapter uses different data and generation/evaluation behavior successfully.
9. Tests cover these behaviors; installation and demo evidence are recorded in `docs/verification.md`.
10. The public release contains newly authored code and synthetic examples only, with a release audit and a clear license. Publication is verified against the remote contents.

## Scope

Begin with a local, single-process implementation and explicit cooperating roles. No paid model calls or services are required. The offline example proves the control loop, not LLM quality, training gains, production-scale throughput, or the safety of arbitrary user data.

Add scale or distributed orchestration only after profiling a real workload. The project does not need a UI, a hosted service, a broad plugin framework, or another language to meet this goal.
