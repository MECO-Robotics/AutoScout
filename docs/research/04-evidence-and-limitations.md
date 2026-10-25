# Evidence, method, and limitations

Checked **2026-09-09 UTC**. This is a bounded research pass, not an exhaustive literature review, security audit, license opinion, or runtime benchmark.

## What was inspected

- Web and GitHub repository searches for FRC automated scouting, video scouting, computer vision, robot tracking, and related applications.
- GitHub metadata and recursive trees for the repositories in [the inventory](repository-inventory.csv), followed by README and selected implementation reads.
- First-person technical disclosures from Teams 334 and 1148. Their deployment and performance statements remain author reports.
- TBA's current public API documentation plus its repository-pinned OpenAPI schema and a checked-in 2026 match fixture.
- FIRST's official documentation and the Postman collection linked by that page.
- Statbotics' OpenAPI and source serializers, plus one live public data request.
- Official YouTube API documentation and TBA webhook documentation.

No fetched repository code was executed. Source files were read in a temporary research directory. No video or model weights were downloaded. Public metadata was sufficient; no authenticated TBA/FIRST request was attempted. Credential-like text incidentally present in upstream source was not used or copied into these documents.

## Evidence strength

| Label | Meaning |
|---|---|
| Source-inspected | Relevant source code was read; execution and correctness remain unverified |
| Documented | The project's own documentation describes a capability |
| Author-reported deployment | A project member reports competition use; not independently reproduced |
| Fixture-backed | Example is from a pinned repository test fixture, not a fresh official response |
| Live-observed | This pass issued the stated public read request and observed its response |
| Inference | Our assessment from the preceding evidence, not an upstream claim |

Repository popularity and last-push timestamps were not used as accuracy evidence. No reviewed vision project demonstrated, in the material inspected, a standardized cross-event benchmark establishing all desired per-robot scouting metrics.

## Notable limitations and failures

| Item | Observation and treatment |
|---|---|
| TBA authenticated data | Not queried; API contract and fixture examined instead |
| Direct TBA schema fetch through Python | HTTP 403; obtained the schema from pinned official GitHub source; browser had read the hosted schema earlier |
| FIRST 2026 score response | Not queried; published collection's Score Details examples did not include 2026 |
| FIRST documentation version | Collection endpoint URLs use v3.0 while some prose/examples are older; selected contract needs verification at implementation |
| Statbotics | OpenAPI HTTP 200; `/v3/team_year/254/2026` HTTP 500; do not generalize one sample to all endpoints |
| Nexus direct documentation | Page available but readable contract not recovered; no detailed direct API claims made |
| FRC-7790/FRC-AutoScout | GitHub metadata/search found the repository, but tree retrieval returned HTTP 409; no implementation assessed |
| Project Vector | Disclosure says private; no public source verified during this pass |
| License metadata | GitHub returned null for some repositories with license files; ScoutingPASS and Scoutradioz license text was checked directly |
| Source versus README | Team 334's README mentions files absent from the checked tree; model/checkpoint and client availability must be verified separately |
| Dataset claims | Trees contain training assets in several candidates, but access, provenance, license, split quality, and cross-event diversity were not audited |

## Reproducibility artifacts

`evidence/` contains repository metadata at the sampled revision, a retrieval log, selected API contract excerpts, and a fixture example. These are research evidence, not vendored application dependencies. The CSV records pinned GitHub revisions. The metadata retains the SHA returned by the tree lookup and a separately resolved commit revision. Selected file paths are retained alongside the total file count; the snapshots are not complete repository mirrors.

Verification found no broken local document links. All 15 distinct pinned GitHub file citations resolved through their raw-source counterparts. All 15 TBA paths in the endpoint table exist in the inspected schema. The results are recorded in `evidence/link-check.json`. Endpoint observations are point-in-time, not uptime guarantees.

## Questions this pass leaves open

1. Which season, event(s), and camera source should define the first benchmark?
2. Is dedicated camera capture available, or must the system use broadcasts only?
3. How much human correction per match is acceptable, and how soon must results be ready?
4. Can the most relevant projects provide explicit reuse terms for code, datasets, and model weights?
5. What proportion of target matches has usable video, 2026 score details, and optional Zebra data?
6. Which metric errors actually change alliance-selection or match-strategy decisions?

These are future research/implementation decisions; none blocks delivery of this research pack.
