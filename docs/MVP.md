# AutoScout MVP architecture

The primary workflow is unattended GPU scouting: start the local app, and downloaded matches are queued automatically. The dashboard shows estimated alliance fuel, team contributions when supported, unassigned scoring, robot positions, and reconciliation evidence. No Analyze button or manual label is required to start the primary pipeline.

## Components

| Module | Responsibility |
|---|---|
| `tba.py` | Authenticated TBA API ingestion, or explicitly labeled cached public-page fallback |
| `media.py` | Linked video downloads, MP4 metadata/provenance, frame extraction |
| `worker.py` | Single process-level GPU queue lock, automatic scheduling, subprocess supervision, two-hour deadline |
| `automatic.py` | Every-frame CUDA fuel inference, robot inference/OCR, score readings, archives, reports |
| `scoring.py` | Motion association, repeated OCR validation, hub geometry, identity voting, conservative reconciliation |
| `app.py` | Local FastAPI UI, footage range responses, progress/results, observations, exports |
| `store.py` | SQLite matches, processing state, observations, and audit history |
| `ml.py` | Earlier sampled GPU object-detection diagnostic, still available from CLI |

See [automatic pipeline details](AUTOMATIC.md) for model scheduling, data semantics, processing limits, and evidence files.

## Official data

The [TBA v3 API](https://www.thebluealliance.com/apidocs/v3) supplies team matches, event metadata, alliances, video links, and season-specific score breakdowns when a key is configured. Without a key, public team/match HTML is cached and parsed. The current 25-match dataset uses that fallback. The live authenticated path has not been exercised with credentials.

HTML phase fuel values remain labeled as displayed values; exact API count/point pairs are not invented. Raw API breakdowns are retained when available. Alliance scoring references remain separate from inferred team contributions. Official-data revisions are audited.

## Score semantics

Automatic alliance fuel estimates come from dedicated broadcast fuel-counter OCR. Total score deltas are not treated as fuel because tower and penalty points can contribute. Visual hub-crossing candidates are reconciled with OCR score-update intervals. The model does not create extra ball trajectories to match a score.

When the observed visual count is smaller than the score delta, unsupported fuel remains unassigned. When the visual count is larger, identified shares are reduced proportionally. Fractional rounding is constrained to conserve the total. A debounced score-update interval can combine multiple physical volleys, especially across edits. Matching an official alliance score does not establish correct per-robot attribution.

Manual observations remain optional validation data. Pending proposals do not contribute to reviewed metrics. Accepted observations without team identity may contribute only to an alliance review total. Team accuracy describes labeled attempts, not the entire match. The earlier manually calibrated phase comparison still requires confirmed timing; the automatic counter-based pipeline does not require those markers.

## Evidence and evaluation

Automatic run folders retain compressed every-frame detections, display overlays, robot histories, OCR readings, crossing candidates, reconciled shares, model hashes, and timing/coverage statistics. `scripts/refresh-reconciliation.py` can recompute derived shares from retained evidence while preserving the original report and verifying archive frame coverage.

Validation includes fifteen automated tests for source parsing, unknown/missing data, review isolation, input/path validation, motion tracking, OCR stability, score conservation, synthetic video/evidence, rerun behavior, and range playback. A delayed-response browser test verifies that switching matches cannot attach one match's overlays to another. Desktop/mobile captures show the automatic dashboard with no page-width overflow or JavaScript errors.

The source is 60 fps for Orlando qualification 6. A 10-second benchmark analyzed all 600 frames in 39.59 seconds on the Quadro P600. Full-run reports record actual completion time. The two-hour supervisor limit is enforced; a timeout remains a failure with partial evidence rather than being reported as complete.

No held-out per-robot accuracy benchmark is established. Hub geometry is tuned to the current 2026 wide-view broadcast profile. OCR, robot detection, trajectories, and identity association remain experimental. Missing shots, cycle time, defense, and field-meter localization are not yet automatically reported.

## Local operation

The app binds to loopback and has no multi-user authentication. The server must remain running for the queue to continue. New downloads are picked up automatically. Completed matches are cached, interrupted jobs restart, failed jobs remain visible, and low disk space pauses scheduling. Uploads accept MP4 up to 300 MB; compatible video codecs are required. TBA page and video-extractor changes can affect ingestion without invalidating already downloaded footage.
