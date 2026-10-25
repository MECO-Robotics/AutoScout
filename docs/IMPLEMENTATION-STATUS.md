# Attribution plan implementation status

September 10, 2026. Existing pretrained weights only; no training or fine-tuning.

## Delivered in this iteration

| Area | Behavior and evidence |
|---|---|
| Review workflow | Simplified team table and full-width playback; advanced diagnostics and manual tools collapsed. Robot tagging is optional, roster-constrained, time/run/camera-scoped, editable and undoable. Browser checks covered desktop/mobile and actual save/edit/undo. |
| Identity corrections | Tags update supported cached crossing attribution without overwriting the original report. Unsupported or conflicting identity remains unknown. Default tag interval follows the selected contiguous visible segment. |
| Statbotics | Current match `pre_epas` adapter, verified 2026 fuel components, retrospective event/year fallback, cache, conditional alliance allocation. Statistical fuel estimates and observed evidence stay separate. Live source records are currently unavailable; the UI does not invent values. |
| Match end | Full-clip scoreboard prepass, coherent final countdown and repeated zero, initial five-second buffer, full-clip fallback on uncertainty or contradictory clocks. Recent unresolved flight evidence extends inference. Tail scoreboard readings remain available. |
| Coverage | Reports distinguish decoded source frames, GPU inference frames, analyzed/skipped ranges and cutoff evidence. Archive retains explicit skipped-tail records, avoiding stale playback boxes. |
| Robot tracking | Motion assignment now gates impossible matches before assignment and adds an HSV appearance cue. Adaptive sharp-crop OCR prioritizes unresolved identities; short gaps retain tracks. This is not full cross-camera re-identification. |
| Flight attribution | Repeated departure evidence replaces image-upward-only launch assignment; ambiguous source candidates remain explicit. Ball gaps tolerate eight frame intervals. Entry candidates require a descending approach. Same-source flight evidence is grouped into physical-volley candidates. |
| Camera geometry | Cut segments and hub geometry are archived; both hubs are retried each second. Fixed wide-view geometry remains experimental and is not a general camera classifier. |
| Inference | Main camera is cropped before fuel inference using the existing weights. Five-frame comparison showed four cropped samples still reached the 300-box cap; this is not a recall benchmark. |
| Evaluation | Six pinned historical runs, read-only diagnostics/reconciliation replay, optional externally verified individual count labels. No fabricated labels or accuracy claims. |
| Operations | Saved reports remain available during reruns. Queue pauses visibly on low disk and resumes automatically with sufficient capacity. In-flight processing also stops before disk exhaustion. |

## Validation

- 43 automated tests passed across the full suite and final regression check; coverage includes identity association, ambiguous launches, entry gaps, match-end edge cases, tag correction/undo and stale runs, prior mapping and score conservation.
- An end-to-end test with controlled detector outputs verifies that GPU cutoff retains later scoreboard changes and produces explicit archive/overlay gaps.
- Real P600 smoke run: 720/720 frames (12 seconds of footage), 57.12 seconds total; scoreboard prepass 23.01 seconds and GPU/tracking stage 33.60 seconds. 126 frames reached the cap; track 10 acquired team 8324. These figures do not measure shot attribution accuracy.
- Full-match q6 v2 validation completed in **935.20 seconds (15 min 35 sec)**: 11,367 frames decoded, 8,491 GPU-analyzed, 2,876 explicitly skipped after 141.5 seconds. Sequential archive coverage and empty skipped-tail overlays were verified. This is slower than the historical v1 run (831.77 seconds), despite fewer GPU frames, because the pipeline adds a scoreboard prepass and identity work.
- Sampled identified-robot coverage increased from 15.0% to 26.6%, but **none of 77 crossing candidates had a known team**; all fuel remained unassigned. This run does not demonstrate improved automatic shot attribution. The cap still affected 70.7% of GPU frames. See [full v2 diagnostic result](research/gpu-v2-full.json).
- Validation exposed stale launch associations on long-lived tracks. Subsequent source-age checks prevent manual tags from crediting those stale links; original reports remain unchanged. That guard is covered by regression tests, not a second GPU full run.

See [benchmark manifest and evaluation instructions](research/attribution-benchmark.md), [crop comparison](research/crop-benchmark.json), and [GPU smoke report](research/gpu-v2-smoke.json).

## Remaining work and limits

The plan's accuracy targets have **not** been met or demonstrated. Human-verified individual shot/count labels and cross-event held-out evaluation are still needed. The current benchmark pins already processed Orlando matches and cannot establish unseen-event performance. These limits prevent declaring the full accuracy plan complete; this iteration delivers the first usable implementation and its evaluation tools.

Drawing a new box to recover a robot entirely missed by the detector is not implemented; tagging currently selects an existing track. Reruns preserve old tags but do not automatically migrate them onto new track IDs.

Full offline cross-camera tracklet stitching, flight-curve reconstruction through long occlusions, synchronized alternate-view fusion, and joint probabilistic allocation of overlapping physical volleys remain future work. Current reconciliation conservatively caps known visual crossings and leaves unseen contributions unassigned. The new physical-volley groups are diagnostic evidence, not a replacement for that validated conservation behavior.

Existing model selection currently retains the pinned weights. Crop benchmarking is a first comparison, not proof these weights are optimal. Statbotics availability is an external dependency; its prior alone never establishes a robot's identity or actual scored shots.

## Statbotics availability check

The correct match and team-event endpoints returned HTTP 500 with empty objects during verification. The [official CSV archive season index](https://github.com/avgupta456/statbotics-csvs/blob/02113df5bc7c66655fd0496ead62ad4fc5212283/v3/years.csv) ends at 2024; no official 2026 archive fallback was found. The adapter is implemented and tested with schema-based fixtures, but cannot provide live 2026 approximations until usable source data is available.
