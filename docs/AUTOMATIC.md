# Automatic scoring pipeline

The app starts a single GPU worker at startup. It automatically processes downloaded matches and updates the dashboard without an Analyze button. Matches are processed sequentially; completed results are cached by pipeline version. A new version queues older results for reanalysis while retaining the prior report during processing. Restarting the server restarts interrupted work, while failed matches stay visibly failed. Keep the server running for the queue to continue.

## What the result means

| Dashboard field | Source | Interpretation |
|---|---|---|
| Estimated alliance fuel scored | Repeated OCR of the dedicated broadcast fuel counter | Scored fuel reported by the broadcast; not a sum of object boxes |
| Raw crossing candidates | Every-frame fuel detector and inferred hub geometry | Experimental visual evidence, including false positives and missed crossings |
| Estimated team contribution | Identified visual crossings reconciled with scoreboard deltas | An estimate bounded by evidence, not an official individual score |
| Unassigned | Score delta with insufficient visual or identity evidence | Remains unknown; never split evenly among robots |
| Robot positions | Robot detector, motion association, and roster-constrained OCR voting | Normalized image positions; track IDs can fragment or switch |
| TBA reference | Cached official score breakdown | Alliance validation reference, not training truth for robot attribution |

The dedicated fuel counters avoid treating tower scores or penalty points as balls. Main scoreboard total values are also retained in the OCR evidence. Counter decreases are ignored, jumps are bounded, and two repeated readings are required. These safeguards reduce OCR noise but do not establish a measured accuracy rate.

A volley record describes a debounced score-update interval. It may combine shots from more than one robot or include unseen activity across an edit. It is not guaranteed to be a single physical volley.

If the scoreboard delta exceeds the visual count, the unexplained excess stays unassigned. If visual crossings exceed the delta, identified contributions are scaled down proportionally. No TBA score is used to silently force a match.

## Version 2: models and scheduling

- Fuel: existing pinned frc9550 YOLO26n weights, CUDA, 960-pixel inference. A single full-width main-view band (17–67% of frame height) is cropped **before inference** so alternate camera tiles do not compete for the 300 detection slots. All retained match-window frames receive inference.
- Robots: existing pinned RobotTracking weights, six detector updates per video second. Position estimates are held between updates. Motion association now adds a small HSV appearance histogram as a supporting cue; it does not establish team identity or recover identities across camera cuts.
- OCR: RapidOCR PP-OCRv4 mobile models on CPU. The full-clip scoreboard prepass samples twice per video second. Robot-number OCR prioritizes unresolved tracks and sharp crops: unresolved identities become eligible every 0.6 seconds, resolved identities every 2.5 seconds, with at most one eligible robot read per frame. Eligibility does not guarantee that every robot is read at that rate.
- Launch association: accumulate competing source votes near the start of a moving ball track, using an expanded region above bumper detections and departure motion. It no longer requires upward image motion. Ambiguous sources remain unknown.
- Entry evidence: require a multi-observation descending approach to the inferred rim. This is still a crossing candidate, not verified scoring.
- Geometry and tracking: retry hub geometry every second and record its history. Visual-change camera cuts clear tracks. Ball gap tolerance is eight frame intervals; robot gap tolerance is 1.2 seconds. Neither is full offline trajectory reconstruction or robust camera recognition.
- Volley diagnostics: group nearby launches from the same source track. These groups are diagnostic; conservative scoreboard reconciliation still governs reported contribution estimates.

No model training or fine-tuning is performed. The compressed archive records every decoded frame, marking frames that intentionally skip detection. Dashboard overlays are sampled twice per video second; this display sampling does not reduce inference coverage inside the retained window.

## Match end and coverage

The CPU scoreboard pass inspects the complete clip before choosing a cutoff. It requires a coherent clock history starting at 60 seconds or more, at least 30 seconds of observed countdown, a near-zero reading, and three zero readings spanning at least one second. Autonomous zero, missing clocks, long OCR gaps, impossible jumps, and contradictory later positive clocks cannot authorize an early stop. Unsupported layouts or uncertain histories retain full-clip detection.

A confirmed end retains an initial five-second buffer. Recent unresolved moving launch-linked or near-hub tracks can extend it; sustained uncertainty restores full-clip processing. This heuristic does not guarantee that all unobserved late flights are preserved. Full-clip OCR remains available for delayed score updates even when tail GPU inference is skipped.

`frames_processed` counts frames receiving GPU inference; `frames_decoded` counts all decoded frames. `all_frames_analyzed` means full-clip inference. `match_window_analyzed` means a completed retained-window pass with explicit tail skips. `inference_ranges` and `skipped_ranges` are inclusive zero-based frame ranges. `match_window` records timing evidence and the fallback reason; `stage_times` separates the OCR prepass and main analysis. Potential skipped footage duration is not a measured GPU time saving. Version 1 reports retain their original every-frame semantics.

## Robot tags and statistical approximations

The summary keeps video-supported contributions and Statbotics approximations distinguishable. A Statbotics lookup prefers `/v3/match/{key}` pre-match EPA components, then team-event and team-year aggregates. The 2026 component mapping is pinned in `autoscout/priors.py`. Aggregate fallbacks are retrospective and may contain later results. Responses are cached for one hour. Missing records, unavailable service, or incompatible fuel components remain unavailable; total EPA is never converted directly to ball counts.

When compatible fuel components exist for all three alliance members, the approximation allocates the TBA alliance fuel reference in proportion to their fuel expectations. Otherwise it can display an expected fuel average without pretending it is this match's production. Statistical values do not identify robots, change video-supported contributions, or fill the evidence-based unknown bucket.

During playback, open robot tagging and choose a detected box or its track from the selector, select the team and interval, then save. Edit and undo are supported. Tags are stored separately from generated reports and scoped to the analysis run, track, time range, and available camera segment. Only cached crossings already linked to that source can gain a corrected identity. For version 1 evidence without launch timestamps, scoping uses crossing time. Conflicts remain visible and unresolved. Tags do not fabricate scoring, propagate automatically to a new run, or reconstruct missed trajectories. Drawing a missed robot and targeted reconstruction remain future work.

## Processing limit

There is no maximum processing time. A timeout is not generated by the analysis pipeline; partial compressed evidence and progress remain available if the process is stopped externally. The runtime in the final report includes model loading, the full-clip OCR prepass, inference, and tracking.

The historical version 1 10-second benchmark processed all 600 source frames in 39.59 seconds on the Quadro P600. Use the full-run report for actual per-match runtime and frame coverage. Other recordings and hardware may differ. The system enforces a deadline, not a guarantee that every source will complete successfully within it.

## Artifacts

For each run, `data/automatic/<match>/<run>/` contains:

- `frames.jsonl.gz`: timestamped fuel boxes/confidence, ball track IDs and source votes, camera segment/cut markers, and robot observations; intentionally skipped tail frames carry `inference_skipped` instead of detections.
- `report.json`: score readings, deltas, crossing candidates, reconciled team shares, robot history, identity coverage, model hashes, and processing statistics.
- `overlay.json`: display-sized sample for synchronized video evidence.

Worker logs are in `data/automatic/<match>.log`. The JSON dashboard endpoint is `/api/matches/<match>/automatic`; `?overlay=true` retrieves overlay data. Previous and partial runs remain on disk. Low free disk space pauses the queue.

## Limits

The current broadcast geometry is tuned to the 2026 footage in this library. Robot detection, number OCR, and trajectory matching remain experimental. A team can be identified in some frames without enough evidence to attribute its shots. Occluded, blurred, and low-confidence fuel may be missed; dense frames can reach the 300-detection cap. Broadcast cuts cannot be reconstructed by analyzing every available frame. No held-out per-team accuracy benchmark has been established.

## Verified full-match run (historical version 1)

Version 2 q6 completed in **935.20 seconds**: 11,367 frames decoded, 8,491 GPU-analyzed, and 2,876 post-match frames skipped. Its 77 crossing candidates had no known team assignments, so attribution remains unvalidated. See [implementation status](IMPLEMENTATION-STATUS.md) and [v2 report summary](research/gpu-v2-full.json). The following measurements are **version 1**, not validation of the new heuristics.

Orlando qualification 6 completed in **831.77 seconds (13 min 52 sec)** on the Quadro P600. All **11,367 source frames** were confirmed in the compressed archive. The automatic worker then started qualification 18 without a button press.

The result retained **133 blue / 41 red** fuel from OCR, compared with **141 blue / 41 red** TBA fuel points, and **29 blue / 9 red** raw crossing candidates. The OCR/reference gap is visible; these are different measurements. Repeated robot identities included 8324 and 7431. Conservative reconciliation credited an estimated **1.33** fuel to identified 8324 crossings, leaving **131.67 blue / 41 red** unassigned. This is limited observed attribution, not an estimate of 8324's complete match production. **8,115 frames reached the 300-box cap**, another substantial limitation on visual coverage.

This benchmark establishes unattended execution, every-frame processing, evidence retention, and performance under the two-hour limit on one match. It does not establish adequate per-robot scoring accuracy.

## Reproducible diagnostics

Run `.venv/bin/python scripts/evaluate-attribution.py --replay` for read-only metrics and cached reconciliation against the six pinned baseline reports. Add `--latest` for current reports. See [benchmark scaffold](research/attribution-benchmark.md) and [manifest](research/attribution-benchmark.json). Human count-label input is supported, but no ground-truth labels or demonstrated shot accuracy are supplied. The initial six-match scaffold is Orlando only; cross-event evaluation remains pending. Main-view cropping can still hit the 300-box cap and requires labeled airborne recall evaluation.
