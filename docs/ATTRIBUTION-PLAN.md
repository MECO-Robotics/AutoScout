# Shot attribution improvement plan

Updated September 10, 2026. Implementation is underway; see [delivered behavior, validation, and remaining work](IMPLEMENTATION-STATUS.md). Accuracy targets below remain proposed gates, not achieved results.

## Outcome

Automatically estimate scored fuel for all six teams, track robot positions, and show evidence and uncertainty on the dashboard. No analysis button or routine user annotation. Analyze every source frame during match play and a post-match scoring buffer for fuel; complete each match within two hours on the available GPU. Development annotations are needed to measure accuracy, but are not part of the dashboard workflow.

Use existing pretrained models only: no custom training or fine-tuning. Development labels support evaluation, model selection, and threshold calibration only. Improve inference crops, tracking, OCR, geometry, and reconciliation around frozen model weights.

The recommended approach is **persistent robot identity → launch and flight evidence → scored-entry evidence → scoreboard-constrained team estimates**. Replacing the detector alone will not fix attribution.

## What the current runs establish

These are pipeline measurements, not accuracy against individually labeled shots. Blue/red ordering applies throughout.

| Orlando match | Processing time | Source frames | Frames reaching 300 detections | Raw crossing candidates | OCR fuel counters |
|---|---:|---:|---:|---:|---:|
| Qualification 6 | 13.9 min | 11,367 | 71.4% | 29 / 9 | 133 / 41 |
| Qualification 18 | 14.4 min | 12,048 | 58.8% | 13 / 5 | 209 / 15 |
| Qualification 24 | 15.2 min | 12,870 | 50.3% | 3 / 45 | 63 / 66 |

Qualification 6 attributes only an estimated 1.33 fuel to 8324; most scoring remains unassigned. Its OCR blue counter also differs from the TBA fuel reference, 133 versus 141. Agreement on alliance totals would still not establish correct team attribution.

Sources: completed `report.json` artifacts under `data/automatic/`; [current pipeline](../../autoscout/automatic.py), [tracking and reconciliation](../../autoscout/scoring.py), and [automatic pipeline documentation](../AUTOMATIC.md).

## Diagnosed bottlenecks

1. **Detection capacity is spent outside useful trajectories.** Fuel inference runs on the entire composite broadcast frame with a 300-box limit. Main-view filtering happens afterward. Floor fuel and alternate camera tiles can compete with airborne fuel. Cap frequency is a warning signal; annotated recall must establish which objects are actually lost.
2. **Identity evidence arrives too slowly.** Robot detection runs at 6 Hz, tracks expire after 0.8 seconds without association, and number OCR runs every three seconds. Identity needs repeated votes, so short track fragments often never get a team number. Held positions between detections also weaken launch association.
3. **The launch rule is too restrictive.** It requires upward image motion inside exactly one expanded robot box and permanently latches that source. Shooter exits can be above bumper-like detections; perspective can make valid launches move sideways. Early association errors cannot be reconsidered.
4. **Flight evidence breaks easily.** Fuel tracks tolerate only four frame intervals of missing detections. Distance-based association lacks explicit flight hypotheses, so blur, overlap, and occlusion can fragment or switch tracks.
5. **Goal geometry is fragile.** A color-based gate is inferred for the broadcast layout. Finding one hub prevents retries for the missing hub until a camera cut. A downward crossing of that line is not sufficient proof of a scored ball.
6. **Reconciliation is not a volley model.** It greedily assigns crossings to score-update windows with fixed timing tolerance. Broadcast updates can lag or combine multiple shooters. It cannot reconstruct missing launch evidence or determine team identity from an alliance delta alone.

7. **Post-match footage still receives full inference.** There is no match-end state machine; expensive detectors run through the entire clip.

## Implementation sequence and gates

### 1. Establish a benchmark and replay diagnostics

Select six complete matches across Orlando and Tallahassee, including simultaneous shooters, distant robots, motion blur, occlusion, and camera cuts. Use three for development, one for confidence calibration, and two untouched tests; keep adjacent frames from the same match in the same split. Expand the test set before claiming cross-event reliability.

Label robot identities and track segments, launch/volley intervals, visible goal entries, misses, scoreboard changes, and periods where attribution is not observable. Mark ambiguous labels explicitly and independently review a sample. Annotate dense frame windows around representative shots rather than every ball on the floor.

Add per-stage diagnostics: detection recall near launches and hubs, track fragmentation, identity coverage during shooting, source association correctness, entry precision/recall, score timing error, and final attribution. Persist ball track IDs, camera segments, hub calibration, candidate associations, and rejection reasons. Replay tracking and reconciliation from cached boxes; repeat inference only when detector inputs or weights change. Existing archives omit ball IDs and cut flags, so some replay preparation needs another video decode.

**Gate:** reproducible baseline and a ranked breakdown of where labeled shots lose their attribution. Version configuration, labels, models, and outputs together.

### 2. Detect match end and avoid unnecessary inference

Add a lightweight scoreboard pass before expensive detection to establish match phase and clock history. Confirm final-phase 0:00 using repeated consistent readings and preceding countdown evidence. Distinguish the end of autonomous from the end of the match. A missing clock, camera cut, isolated OCR zero, or replay is not sufficient to stop analysis. If phase or end time remains uncertain, process the full clip.

Continue every-frame fuel inference and robot tracking for an initial five-second buffer after the confirmed end. This is a configurable engineering starting point, not a claim about scoring eligibility; validate it against late trajectories and broadcast delays. Extend the buffer when unresolved flight evidence requires it. Continue lightweight scoreboard OCR through the remaining footage to capture delayed updates and final totals, without counting replayed action again. If later clock evidence contradicts the cutoff, invalidate it and process the skipped interval.

Record the inferred end, confidence/evidence, buffer end, GPU-analyzed frame ranges, skipped ranges and reasons, and measured time saved. Update report/API/dashboard coverage semantics: distinguish full match-window coverage from full-clip coverage, and intentional post-match skips from decode failures or timeouts. Preserve existing reports under their original semantics. A delayed score delta can still reconcile with pre-cutoff trajectories.

**Gate:** no labeled match action or late scoring trajectory is truncated on the evaluation set; ambiguous footage falls back to full processing. Test autonomous 0:00, clock resets, missing overlays, post-match replays, delayed score changes, and recordings that begin mid-match. Report actual GPU time saved rather than projecting savings from clip length alone.

### 3. Preserve team identity and shooting activity

Use offline tracklet stitching with motion, appearance, alliance color, and roster-constrained OCR. Select sharp, large bumper crops for OCR as tracks develop instead of waiting for a global three-second timer. Aggregate consistent evidence across linked fragments; use future frames to resolve earlier identities. Do not carry identities across camera cuts without independent supporting evidence.

Represent robot body/shooter regions separately from bumper-number regions using existing pretrained detections and geometric regions; do not require a newly trained shooter detector. Increase robot detection frequency around suspected shooting activity, with interpolation elsewhere, and benchmark its runtime cost. Retain multiple possible shooters until flight evidence resolves them; allow revisions instead of permanently accepting the first nearby robot.

**Gate:** improved correctly identified shooting-time coverage and fewer identity switches on the development set, without increasing incorrect team assignments. Report image-coordinate trajectories first; field coordinates require separate camera calibration.

### 3a. Optional robot tagging in playback

Allow the reviewer to select a robot bounding box at the current playback time and choose a team from the match roster. If the detector missed the robot, allow drawing a box to seed a track for that interval. Tagging is optional; automatic processing and initial estimates never wait for it.

Persist each tag with match key, analysis run, camera segment, track ID (when available), timestamp/range, selected team, and manual provenance. Apply the identity to the continuous track segment and confidently linked fragments, including earlier frames where supported. Do not propagate blindly across cuts or suspected identity switches. Conflicting tags and simultaneous incompatible identities must remain visible for correction. Provide edit/undo and preserve an audit history; keep manual tags separate from generated reports so reruns cannot silently discard or misapply them.

Recompute affected source associations and reconciled contributions from cached evidence after a tag changes. A team tag establishes identity, not proof that every nearby ball was shot or scored by that robot. Show the tag's affected interval and resulting count change. If cached data cannot support reconstruction, queue the necessary targeted analysis automatically and show pending status.

**Gate:** tagging a known shooter updates only supported events, undo restores the previous estimate, and tags remain correctly scoped after seeking, camera cuts, and analysis reruns.

### 3b. Statbotics approximation before video attribution

Fetch and cache Statbotics estimates for all six teams to display an initial contribution estimate while video analysis runs. EPA predicts average scoring contribution; it does not report measured individual shots. Use the relevant season's documented fuel component when available, preserving its units and phase breakdown. Never convert total EPA, which may include other scoring, directly into ball counts.

Implemented schema adapter: fetch `/v3/match/{match}` once and read `pre_epas[team]`; the upstream TeamMatch table and endpoint were removed, so the former `/v3/team_match/...` 404 did not establish match-data absence. The pre-match dictionary uses `epa` for total points and `comp_0_epa`, `comp_2_epa`, `comp_3_epa`, `comp_4_epa`, and `comp_5_epa` for auto, transition, first-shift, second-shift, and endgame scored fuel. Event/year fallbacks use `epa.breakdown` with those named fuel components and explicitly indicate retrospective aggregates. Require every component to be finite and nonnegative; do not trust a derived sum that may hide missing values. These are scored hub fuel points (one per scored fuel), excluding tower and penalties. Preserve phase breakdown, raw response, fetch time, temporal basis, and pinned schema provenance. Never read post-match `epas` as a pre-match prior.

The API currently returns empty/error data for the tested team-year request; upstream [issue 414](https://github.com/avgupta456/statbotics/issues/414) reports a data-layer outage. Missing records are cached for one hour and leave the prior unavailable while video analysis continues. When records return, the implemented adapter computes the conditional statistical allocation from current official alliance fuel totals; cached prior refresh and updated official totals are handled independently.

When compatible fuel estimates exist, initialize relative contribution weights within each alliance. Once an alliance fuel count is available, a simple baseline approximation is `alliance fuel × team fuel estimate / sum(alliance team fuel estimates)`. This is a statistical allocation, not observed attribution. Require valid compatible values for all three teams and a positive denominator; otherwise retain an unavailable prior instead of inventing zeros or an equal split. Preserve the raw prior and source separately from later results.

Refine this baseline using tagged/recognized shooters, shooting intervals, linked entries, and scoreboard timing. Strong visual evidence overrides the prior. Keep an explicit unknown bucket in evidence-based reconciliation; do not assign every unexplained ball just to match the initial statistical split. Present distinct fields for **Statbotics approximation**, **video-supported contribution**, and **unassigned fuel**, with provenance and update time. Team tags resolve visual identity; EPA must not decide which physical robot is which.

Evaluate Statbotics-only, video-only, and combined estimates against held-out individual labels. Use historical pre-match values for evaluation where available, and flag retrospective fallbacks to avoid future-result leakage. Because Statbotics and TBA share match-result information, agreement with TBA is not independent validation of this approximation. No custom model training or fine-tuning is introduced.

Sources: [Statbotics project and EPA definition](https://github.com/avgupta456/statbotics), [official API client documentation](https://statbotics.readthedocs.io/), and [verified 2026 component mapping](https://github.com/avgupta456/statbotics/blob/a2cea5553e35693d423400f419bd770cb2143408/backend/src/breakdown.py), [pre-match EPA serialization](https://github.com/avgupta456/statbotics/blob/a2cea5553e35693d423400f419bd770cb2143408/backend/src/models/epa/main.py), and [match endpoint](https://api.statbotics.io/v3/match/2026flor_qm6).

**Gate:** initial estimates appear automatically when compatible data exists; missing or stale data is clearly labeled; video evidence and manual identity corrections can change the result without being forced back to the prior.

### 4. Recover airborne fuel and complete trajectories

Crop the primary camera before inference. Evaluate overlapping shooter/flight/hub crops to preserve small airborne targets, merge duplicate detections, and retain coverage of the full relevant flight area on every frame. Do not mask away launch paths just to reduce box counts. Compare crop resolution and detector limits using labeled airborne recall and runtime, not total boxes detected.

Stitch short ball tracklets using direction, speed, uncertainty, and locally plausible flight curves. Use offline forward/backward evidence to bridge short blur gaps, keeping alternatives when multiple balls overlap. Avoid a single field-plane homography for airborne balls. Calibrate both hubs per camera segment, retry missing hubs, and invalidate geometry when the view changes. Score entry requires trajectory and goal-region evidence, not merely crossing a horizontal line.

Start with the main view. Add alternate views only after synchronization, camera mapping, and duplicate-event suppression are validated.

**Gate:** launch-to-entry linking improves on labeled shots, including crowded scenes, without a corresponding rise in false entries or wrong shooters.

### 5. Reconcile physical volleys with the scoreboard

Create physical volley candidates from each robot's shooting activity and linked flights. Decode dedicated fuel counters over time, preserving OCR confidence, corrections, and missing readings. Detect scoreboard layout/clock and estimate update delay from clear isolated volleys. Keep total-score changes separate from fuel changes; apply verified phase/scoring semantics before interpreting points as balls.

Jointly reconcile neighboring volleys against observed fuel deltas using candidate shooter activity, linked entries, plausible timing, and an explicit unknown contribution. A delta of 20 with overlapping shooters is a constraint on their combined contribution, not evidence for an equal split. Missing visual balls may contribute to a probabilistic volley estimate only after its error is calibrated on labeled data; otherwise leave them unassigned.

Keep discrete observed events separate from fractional expected counts. Preserve disagreement when OCR and visual evidence cannot be reconciled. Use TBA alliance breakdowns as a separate final validation layer, never as individual-team ground truth or a silent correction.

**Gate:** better per-team count error and useful coverage on held-out matches, not merely better alliance agreement.

### 6. Select existing models for measured remaining failures

Compare available pretrained fuel, robot, OCR, and appearance models on the frozen evaluation protocol. Start with the existing pinned fuel and robot weights and the previously downloaded alternative robot model. Check additional candidates' documented inputs, provenance, licenses, and deployment requirements before adoption; do not assume a generic model recognizes FRC fuel or robot identities.

Benchmark useful airborne recall, identity accuracy, attribution precision/coverage, runtime, and peak GPU memory. Evaluate input resolution, overlapping crops, confidence thresholds, and compatible inference optimizations without changing learned weights. Adopt a replacement only when it improves end-to-end results within the available 2 GB P600 memory and one-hour budget. Keep model versions and rollback artifacts pinned.

If existing models cannot meet a target, document the gap and preserve unknown contributions. Custom training, fine-tuning, training datasets, and training compute are excluded from this plan.

### 7. Simplify the dashboard and review flow

Make the default screen answer three questions: which match is selected, how much each team likely scored, and how much evidence supports those estimates. Keep match selection compact, followed by one six-team contribution table and a clear processing/status line. Place alliance totals and unassigned fuel next to the team estimates so unexplained scoring stays visible.

Show one primary contribution estimate per team with a short source label: Statbotics approximation, video estimate, or video estimate with reviewer-tagged identity. Preserve the underlying statistical and video-supported values in an expandable breakdown rather than presenting competing headline numbers. Unknown values remain unknown; a manual identity tag must not imply that scored counts were manually verified.

Keep playback directly below the summary, with robot boxes enabled and one obvious optional action to tag a robot. Group overlay controls together; allow fuel boxes to be hidden independently. Keep routine playback controls visible. Move raw crossing counts, OCR samples, volley reconciliation, model/GPU details, exports, manual hub calibration, diagnostic runs, and legacy observation forms into a single advanced evidence area with concise subsections. Do not require opening this area to understand failures or incomplete results.

Remove duplicate status messages, repeated caveats, and redundant score tables. Use brief source and uncertainty labels beside the values they qualify, with fuller explanations on demand. Processing, unavailable priors, failed analysis, and completed results should each have a clear state and a relevant next action only when needed. Automatic analysis remains the default; no Analyze button or mandatory review steps.

On mobile, prioritize the selected match, contribution table, and playback without a long queue or technical panels above them. Keep team numbers, unknown contribution, and optional tagging usable without horizontal page scrolling. Preserve keyboard access, readable labels, and native playback controls.

**Gate:** a reviewer can find 8324's estimate and its source, identify unassigned scoring, play the relevant footage, and tag a robot without navigating technical panels. Verify these tasks on desktop and mobile using real completed, processing, failed, and unavailable-data states. Implement this alongside the Statbotics/tagging work so new features do not accumulate as additional dashboard panels.

## Proposed acceptance criteria

These are initial engineering targets, not demonstrated performance. Report sample sizes and uncertainty; a small easy subset cannot establish success.

| Measure | Initial gate |
|---|---|
| Correct team among confidently attributed scored events | At least 95% precision |
| Coverage of human-observable scored events | At least 80%; also report coverage over all scoring |
| Individual team count error | Within max(5 fuel, 10% of labeled count) for at least 90% of evaluable team-match records |
| Ambiguous or off-camera activity | Explicitly unknown; never silently zero |
| Robot tracking | Report identity switches/minute, identity coverage during shooting, and position error on labeled frames |
| Runtime | Target p95 below 45 minutes; every accepted completed run below 60 minutes |
| Match-end cutoff | No labeled action truncated; ambiguous end detection uses the full clip |
| Frame coverage | Every frame in the retained match window and buffer analyzed; skipped tail explicitly reported |
| Automation | Downloaded matches start automatically; dashboard results refresh without user action |

Only evaluate complete team totals where reference labels support them. Also report visible-interval performance separately so off-camera action is neither fabricated nor excluded without disclosure. Calibrate confidence on separate data before exposing a numerical confidence score.

## Compute budget and rollout

Current full-match runs take about 14–15 minutes on the P600, leaving potential headroom, but extra crops and OCR need measurement. Provisional sequential budget: 25 minutes decode/fuel inference, 8 minutes robot identity/OCR, 7 minutes trajectory and volley inference, and 5 minutes serialization/overhead. These are allocations, not benchmarks; retain the existing two-hour supervisor deadline and mark timeouts incomplete.

Profile peak GPU memory and wall time on the longest and most crowded clips. Cache detections and crop features so algorithm experiments avoid repeated GPU passes. Maintain every-frame fuel processing within the retained match window and buffer; skip expensive post-match inference only after the end-detection gate passes. Reduce redundant OCR and use targeted higher-resolution crops within that window.

Run the new version alongside stored baseline results on the evaluation set, then automatically process a small batch before replacing dashboard estimates. Show team estimate, directly observed count, uncertainty/coverage, and alliance unassigned total, with optional evidence playback. The user should normally only read the dashboard. Preserve prior reports for rollback and comparison.

**First implementation milestone:** a simplified summary/playback interface, Statbotics availability/schema verification and initial approximations, optional robot tagging with cached reattribution, benchmark/replay diagnostics, conservative match-end detection with explicit coverage reporting, adaptive robot identity, and pre-inference main-view cropping. These address concrete current failures and provide the evidence needed to select existing models and inference settings.
