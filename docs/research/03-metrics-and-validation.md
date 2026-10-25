# Metric coverage and validation

Research interpretation, 2026-09-09. This document translates [the reviewed APIs](02-api-inventory.md) and [existing projects](01-existing-solutions.md) into a measurement plan. It does not claim these metrics have been implemented or achieved.

## What can be obtained automatically?

| Desired scouting metric | Available without vision | Remaining video/manual work | Appropriate reference |
|---|---|---|---|
| Team/alliance/match identity | TBA roster and match identifiers | Match-to-video alignment; robot-to-team identity | Match record plus reviewed bumper/station labels |
| Autonomous fuel scoring | 2026 alliance `hubScore.autoCount` | Per-robot attribution | Alliance count plus human-labeled robot events |
| Teleop/shift fuel scoring | Alliance phase/shift counts | Per-robot contributions and event times | Matching segment count plus human attribution |
| Attempts, misses, accuracy | No per-robot attempt/miss ledger in inspected TBA fields | Detect all attempts, distinguish missed and unobserved outcomes | Labeled visible attempts and outcomes |
| Shooting rate / burst size | No robot-level public rate field | Detect release sequences; define rate denominator | Annotated bursts; separate attempts from makes |
| Cycle count / cycle time | No direct field | Define intake-to-score or another game-specific cycle | Human event timeline with the same definition |
| Intake source and ferrying | No direct field | Identify source, possession/transfer, and target | Reviewed clips; report ambiguous events |
| Auto path / field heatmap | Optional Zebra coordinates | Homography, tracking, camera-cut handling | Zebra where available plus manually labeled frames |
| Defense time / effectiveness | No direct observed field; DPR is an estimate | Identify interaction and context | Human labels; effectiveness requires a separate definition |
| Inactivity / disabled behavior | No general causal failure diagnosis | Observe movement/activity and visibility | Human video review; inactivity does not prove failure |
| Tower outcome | 2026 station-specific auto/endgame outcomes | Optional visual confirmation | Official station-mapped result |
| Climb attempts / time to climb | Outcome only | Identify attempt onset, retries, completion | Human timeline |
| Fouls committed by a robot | Alliance foul/adjustment data | Specific robot attribution generally unresolved | Reviewed referee evidence if available; avoid guessing |
| Consistency across matches | Can aggregate official outcomes and estimated ratings | Aggregate observed robot metrics with coverage | Multiple matches, uncertainty and missingness reported |

The API columns are grounded in [TBA's schema](https://github.com/the-blue-alliance/the-blue-alliance/blob/4d7b599c56b2f2c21a85ea03e6db9c06ed8ec942/src/backend/web/static/swagger/api_v3.json). Suggested measurements and evaluation choices are our interpretation.

## Validation must have separate levels

1. **Source alignment:** confirm event, match, roster, camera view, and match-relative time. A correct detector on the wrong match is unusable.
2. **Identity:** evaluate whether detections and tracks belong to the correct team, including after occlusion/camera changes. Track longevity alone can reward a consistently wrong identity.
3. **Event recognition:** label attempts, makes, misses, duplicate detections, and unknown outcomes. Measure event precision/recall and timing error against human annotations.
4. **Robot attribution:** measure per-robot count error and scorer identity for matched events. Include simultaneous shooting and blocked robots.
5. **Alliance reconciliation:** aggregate eligible events by alliance/phase and compare with the corresponding official count. Keep human-player or unresolved contributions separate where applicable.
6. **Operational value:** measure review minutes per match, coverage, processing latency, failure rate, and whether results arrive in time for scouting decisions.

Always report raw predictions separately from corrected predictions. Team 334's code includes score-OCR correction; it is a useful integration feature but changes what score agreement can demonstrate. [Correction implementation](https://github.com/derek-pohl/ai-scouting/blob/97184951f9646f047cb5587f4d0aebac8413a729/app.py#L2711)

For example, official alliance fuel = 100 and predicted robot counts = `[60, 30, 10]` can agree perfectly even when the true allocation is `[30, 60, 10]`. This constructed example shows why TBA totals alone cannot validate scouting attribution.

## A useful benchmark before adopting a repository

Use a held-out set spanning multiple events, camera layouts, lighting conditions, robot designs, and scoring rates. Partition by match/event rather than randomly distributing adjacent frames between training and test sets. Otherwise near-identical images can exaggerate generalization.

Include camera cuts, side-view composites, obscured bumpers, overlapping robots, simultaneous shooters, moving shots, hub congestion, offscreen actions, scoreboard changes, and partial recordings. Report excluded and failed matches, not just completed ones. No sample-size or target-accuracy claim is justified until the event distribution and intended decision are chosen.

Annotators should record team, action, timestamp/interval, outcome, visibility, and confidence, with disagreement adjudication. Preserve source video ID/file hash, model revision, calibration, rule version, raw predictions, corrections, and official-result version. Use `unknown` for unobserved activity; reserve zero for a supported observation of no activity.

Suggested summary measures: per-robot absolute count error, event precision/recall, attribution accuracy, identity switches, percent of match observable/tracked, phase-level alliance error, human review time, and end-to-end latency. Avoid treating a single “accuracy” percentage as sufficient.

## Research conclusions

- **Lowest-risk automation:** roster/video discovery, official tower outcomes, score imports, and aggregation of already-reviewed observations.
- **Best evidenced assisted vision use:** humans establish robot identity/paths while computer vision counts high-volume fuel activity; Team 334 reports using this approach in competition. [Retrospective](https://www.chiefdelphi.com/t/building-ai-assisted-frc-scouting-what-worked-what-failed-and-what-we-learned/522442)
- **Hardest gap:** maintaining correct team identity and attributing scores during occlusion and concurrent shooting.
- **Dedicated cameras change the problem:** fixed hub views can improve observable scoring coverage, but synchronized capture and a wide view are still needed for attribution. Broadcast-only performance should be evaluated separately.
- **Cross-season support is not just changing point values:** new objects, geometry, actions, camera layouts, and evaluation labels may be needed.

There is enough existing work to justify an evaluation phase, but the evidence does not justify promising fully automatic usual scouting metrics from arbitrary livestreams.
