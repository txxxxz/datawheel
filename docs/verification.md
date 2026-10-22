# Verification

## Version 0.2.0: configurable model integration

On 22 October 2026, all 24 tests passed on Python 3.14.4. Seven HTTP/domain tests add coverage for separate draft/critic/revision requests, actual feedback delivery, independent admission despite an approving critic, malformed or truncated responses, transport failures, candidate-contract failures, configuration identity, resume without repeated calls, and boolean/integer distinctions in the example evaluator. These tests use only a loopback HTTP server and synthetic responses.

A clean 35-file Git-index snapshot was installed into a fresh virtual environment with `python -m pip install .`. The installed distribution reported version 0.2.0 and imported from `site-packages` outside the checkout. Its 24 tests passed, and the README dialogue, HTTP replay, custom-adapter and resume commands ran successfully.

| Installed workflow | Observed outcome |
| --- | --- |
| Default dialogue, two rounds | 19 exported records |
| Local HTTP replay, two rounds | 6 actual POSTs; 12 exported records |
| Independent uppercase adapter | 17 exported records |
| Default dialogue resumed to three rounds | 27 exported records |

An independent reviewer authored a parcel-query domain, tool schema, evaluator and response server outside this repository. The actual CLI `--adapter-config` path completed two rounds with six HTTP calls without changing package code. A critic asking for every candidate to be admitted could not override a `parcel_world_mismatch` rejection. The server changed its synthetic response only when that reason appeared in the next HTTP request. This proves feedback transmission and the admission boundary; the response change is a programmed fixture behavior, not learned improvement.

Additional independent fault injection checked eight configuration changes and an evaluator source change: each refused resume before sending another request. When the second-round critic returned HTTP 503, the failed attempt retained its two calls. Resume repeated only the uncommitted round's three calls, preserved the first-round hashes, and produced the same final dataset as the deterministic uninterrupted fixture. Completed-run resume sent no further HTTP requests.

The exact 35-file publication candidate was reviewed and scanned for private source paths/identifiers, personal email addresses, private-key headers and common credential patterns; none were found. Synthetic negative tests contain clearly invented credential-shaped values used to verify rejection. Private audits, actual run outputs and environments remain outside the publication.

The [CI workflow](../.github/workflows/ci.yml) installs the package and runs all tests, the dialogue example and the HTTP replay on Python 3.11 and 3.14. Executed runs are available on [GitHub Actions](https://github.com/txxxxz/datawheel/actions).

No actual model, paid service or remote compute resource was used for this validation. The adapter currently supports one explicit unauthenticated text-output chat-completions contract; it does not execute the described tools. A hard termination or an evaluator error after HTTP completion can lose uncommitted call traces, and resume can repeat those calls. See [the exact interface and limits](../examples/model_http/README.md) for the inputs required before measuring real-model effectiveness.

## Version 0.1.0: original local loop

### Behavioral checks

On 22 October 2026, `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 17 tests on Python 3.14.4. The tests cover the dialogue and arithmetic loops, independent evaluation, actual feedback-driven allocation and synthesis, deterministic selection, custom adapters, parent lineage, identifier collisions, malformed imports, and resume integrity.

The feedback causality test holds the request seed and budget constant and changes the supplied feedback. This distinguishes a feedback-driven strategy change from a scripted difference between round numbers.

Independent review additionally used an adapter authored outside the repository and a child process that exited while writing an uncommitted round. After resume, all 25 committed/exported artifacts matched an uninterrupted run byte for byte. Input/configuration changes and altered checkpoint contents were rejected explicitly. These checks cover process interruption, not power-loss durability or concurrent writers.

### Clean installation

A clean 27-file snapshot was exported from the Git index to a new temporary directory. A fresh Python 3.14.4 virtual environment installed it with `python -m pip install .`; imports resolved to the environment's `site-packages`, not the development source directory. No runtime packages were required. The installed command passed all 17 tests and ran the README dialogue, arithmetic, custom-adapter and resume commands.

| Check | Observed outcome |
| --- | --- |
| Dialogue import | 10 input records, 3 admitted, 7 rejected with reasons |
| Round 1 allocation | inventory 6; ticket_status 6 |
| Round 2 allocation | inventory 8; ticket_status 4 |
| Inventory tool-result failures | 3 in round 1; 0 in round 2 |
| Two-round export | 19 records |
| Resume to three rounds | 27 records; existing rounds retained |
| Independent uppercase example | Installed CLI accepted the external adapter; 17 exported records |
| Arithmetic diagnostic | 19 exported records |

The dialogue fixture SHA-256 was `48ff8201b80ac20ee638d6dfa87f88c05414537c1fc4ededc25f81c18c178c90`.

The exact tracked file list was inspected before release. It contained newly authored source, tests, documentation, workflow configuration and synthetic fixtures. Scans found no private-source paths/identifiers, personal email addresses, private-key headers or common credential patterns in those 27 files. Run outputs, environments and private review/source-investigation notes were excluded. See [release-audit.md](release-audit.md) for the scope and limitations of that check.

The [GitHub workflow](../.github/workflows/ci.yml) additionally installs the package, runs the tests, and executes the dialogue demo on Linux with Python 3.11 and 3.14. Its executed results are available under the repository's [Actions page](https://github.com/txxxxz/datawheel/actions).

### Interpretation

The bundled tool world, conversations, generator, and repair policy are synthetic and offline. Passing these checks establishes the mechanics and rule compliance of the local flywheel. It does not establish model learning, natural-language generalization, production throughput, or the correctness of arbitrary custom evaluators.
