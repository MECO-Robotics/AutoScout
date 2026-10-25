# FRC AutoScout research

Research date: **2026-09-09 UTC**. Scope: existing public GitHub projects, available APIs, and the evidence needed to validate video-derived scouting. Research only; no application was implemented, dependencies installed, models run, or external accounts changed.

## Documents

- [Existing solutions](01-existing-solutions.md): video-analysis projects, tracking experiments, scouting applications, maturity, licensing, and reuse candidates.
- [API inventory](02-api-inventory.md): TBA, FIRST, Statbotics, video metadata, and optional position/timing feeds; endpoint and 2026 field details.
- [Metric coverage and validation](03-metrics-and-validation.md): what can be obtained directly, what requires vision, and how to evaluate it without circular validation.
- [Evidence and limitations](04-evidence-and-limitations.md): inspection method, reproducibility, unanswered questions, and source provenance.
- [Repository inventory](repository-inventory.csv): sortable metadata and pinned revisions.

## Findings that affect the project

**Useful components exist; a proven general-purpose replacement for human scouting was not established by this pass.** The best broadcast-video starting point is [Team 334's AI scouting application](https://github.com/derek-pohl/ai-scouting). Its authors report using human robot tracing with automated fuel analysis because robot identity and occlusion were unreliable in real broadcasts. Their field experience is more useful evidence than an untested promise of full automation. [Author's report](https://www.chiefdelphi.com/t/building-ai-assisted-frc-scouting-what-worked-what-failed-and-what-we-learned/522442)

**Team 955 is another substantive implementation to investigate.** Its repository contains fuel trajectory stitching, scoring logic, robot detection/tracking, shot attribution, and per-period robot counts. This pass inspected code but did not reproduce accuracy or throughput. [Source](https://github.com/FRC-Team-955/2026-StreamScouting)

**TBA is useful for both ingestion and validation, but different data has different authority.** The 2026 score schema provides alliance fuel counts by phase/shift and station-specific tower results. It does not provide each robot's fuel attempts, misses, cycles, or defense effectiveness. Its optional match timeseries is explicitly unofficial; Zebra coordinates are a separate optional feed. [API specification](https://github.com/the-blue-alliance/the-blue-alliance/blob/4d7b599c56b2f2c21a85ea03e6db9c06ed8ec942/src/backend/web/static/swagger/api_v3.json)

**Score agreement cannot establish robot attribution.** A model that assigns 30 makes to the wrong robot can still match the alliance total perfectly. Also, an output already adjusted to scoreboard OCR must not be presented as independently validated by agreement with that same scoreboard. This is an inference about evaluation, supported by the score-correction code discussed in the solutions document.

**FIRST and Statbotics have different roles.** FIRST supplies event results after FMS synchronization; its published collection now uses `/v3.0/`. Statbotics supplies estimated contributions and predictions, not observed robot actions. Its OpenAPI document loaded, but a representative live data request returned HTTP 500 during this pass. [FIRST documentation](https://frc-api-docs.firstinspires.org/) · [Statbotics source](https://github.com/avgupta456/statbotics)

## Suggested next decision

Choose between **existing broadcast footage** and **dedicated synchronized cameras** before selecting an implementation. Team 334 is the closest reviewed broadcast workflow; Team 1148's Project Vector is relevant evidence for dedicated cameras, but its disclosure describes a private repository. Keep conventional scouting available for corrections and ground truth. This is a research recommendation, not an implementation commitment.

2026 is used as a concrete API example, not as an assumed requirement to exclude other seasons.
