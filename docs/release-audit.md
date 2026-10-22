# Release scope

Datawheel is newly authored for this repository. Predecessor workflows were inspected read-only to understand the problem; their source, prompts, configuration, credentials, and datasets were not copied. Private source locations and the investigation record stay outside this repository.

The bundled examples are invented fixtures. The dialogue examples use fictional tools and records, not customer or banking data. Built-in generation and the local HTTP response fixture are explicitly offline/mock. Release verification calls only the local fixture, without a paid model or remote compute resource. The configurable HTTP adapter can call a developer's own model endpoint when they explicitly supply one; that capability has not been validated against a real model in this release.

The MIT license covers the newly authored repository material. It does not relicense third-party code, data, or models connected by users. See [the license decision](adr/002-license.md).

## Before publishing a revision

- Inspect the exact tracked file list and diff, including examples and generated metadata.
- Exclude local runs, private investigation notes, virtual environments, build outputs, secrets, and raw external data.
- Search tracked content for credential patterns, private paths/hosts, personal contact details, and copied predecessor identifiers; inspect matches in context.
- Run behavioral tests and the README installation/demo from a clean checkout.
- Publish only to this repository, then compare the remote tree and verify its README, license, source, and tests.

A pattern scan is supporting evidence, not a guarantee that arbitrary future inputs are safe to publish. The library writes run artifacts locally; users must review their own data before sharing those artifacts.

Revision-specific execution evidence is recorded in [verification.md](verification.md).
