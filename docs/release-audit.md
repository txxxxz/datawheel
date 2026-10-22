# Release scope

Datawheel is newly authored for this repository. Predecessor workflows were inspected read-only to understand the problem; their source, prompts, configuration, credentials, and datasets were not copied. Private source locations and the investigation record stay outside this repository.

The bundled examples are invented fixtures. The dialogue examples use fictional tools and records, not customer or banking data. Model-like behavior is explicitly offline/mock; the demo does not call a model service or use a remote compute resource.

The MIT license covers the newly authored repository material. It does not relicense third-party code, data, or models connected by users. See [the license decision](adr/002-license.md).

## Before publishing a revision

- Inspect the exact tracked file list and diff, including examples and generated metadata.
- Exclude local runs, private investigation notes, virtual environments, build outputs, secrets, and raw external data.
- Search tracked content for credential patterns, private paths/hosts, personal contact details, and copied predecessor identifiers; inspect matches in context.
- Run behavioral tests and the README installation/demo from a clean checkout.
- Publish only to this repository, then compare the remote tree and verify its README, license, source, and tests.

A pattern scan is supporting evidence, not a guarantee that arbitrary future inputs are safe to publish. The library writes run artifacts locally; users must review their own data before sharing those artifacts.

Revision-specific execution evidence is recorded in [verification.md](verification.md).
