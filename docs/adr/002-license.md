# ADR 002: MIT for broad reuse

Status: selected for the newly authored project under the owner's authorization to publish an open-source repository.

| License | Main effect | Fit here |
| --- | --- | --- |
| [MIT](https://opensource.org/license/mit) | Permissive reuse, modification, and distribution; preserve copyright and permission notices. No explicit patent-license clause. | Recommended: short and straightforward for a small reusable library. |
| [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) | Permissive, with an explicit contributor patent grant and patent-litigation termination; additional redistribution/notice requirements. | A reasonable alternative if explicit patent terms become a priority. |
| [AGPL-3.0](https://choosealicense.com/licenses/agpl-3.0/) | Strong copyleft, including source-availability obligations for modified network-served versions. | A different goal from minimizing integration friction. |

Choose MIT because the intended outcome is easy adoption and reuse, including commercial integration. The root `LICENSE` is the governing text; this comparison is only a short rationale.

The choice applies to the newly authored code and bundled synthetic fixtures. It does not grant rights to a user's input data, connected model, model weights, or third-party code. No private predecessor implementation or dataset is included. No new provider account, paid service, or provider contract is accepted by this choice.
