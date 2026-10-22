# ADR 001: Python first

Status: accepted.

## Context

The first user is a developer bringing datasets, Python evaluation code, and possibly a local model. The first acceptance target is a reproducible, inspectable local loop. No measured workload currently establishes a CPU bottleneck.

| Option | Ecosystem and entry cost | Performance and maintenance | Decision |
| --- | --- | --- | --- |
| Python | Direct integration with common data/model code; familiar virtual environments; a small standard-library core needs no runtime service. | Interpreter overhead and in-memory data limit scale, but neither is a measured blocker for this first loop. | Choose. |
| Rust | Strong compile-time guarantees and a distributable native binary; contributors must learn a second toolchain if their model is in Python. | Useful for measured CPU-bound parsing or transformations. Writing model/data glue adds cost now. | Defer. |
| Python + Rust | Retains Python adapters while moving selected hotspots to native code. | Adds bindings, cross-platform builds, packaging, and two debugging environments. | Defer until profiling justifies it. |

## Decision and consequences

Use Python 3.11 or later and start with the standard library for the runtime. Keep records and adapters explicit, and persist ordinary JSON/JSONL artifacts. This keeps installation and integration small and lets users inspect evidence without our runtime. Zero dependencies is not a requirement: choose a mature library when a concrete need makes it simpler and more reliable than maintaining our own substitute.

The first implementation is single-process and intended for modest datasets. Measure memory, parsing time, and generation/evaluation cost on a representative workload before adding streaming, concurrency, or native extensions. A slower benchmark alone is insufficient: the optimization must improve the actual bottleneck enough to justify its maintenance cost.
