# Airborne filter diagnosis — 2026-09-10

Read-only diagnosis of saved reports and current rendering; no thresholds or production evidence changed.

## Missing evidence is presented as an empty filter

QM42, QM50, QM68 and QM76 currently reference auto-v1 reports whose archives have no ball_tracks records. The playback builder nevertheless marks trajectory_version=2 and writes flights=[], and the UI uses that version as its availability check. Thus unavailable classification is incorrectly presented as zero qualifying fuel. Rebuilding overlays cannot recover missing tracking histories; these matches need analysis with the newer pipeline, or an explicit tracking reconstruction pass.

QM6/18/24/30 have respectively 80/99/125/140 accepted arc fragments in their currently displayed reports. QM6 is reprocessing, so its displayed evidence remains the saved earlier report.

## QM30 rejection audit

Replayed the production builder in a temporary directory, substituting a diagnostic classifier with identical thresholds. No source artifacts were changed.

| First failing criterion | Track segments |
|---|---:|
| Curves in wrong image-space direction | 7,215 |
| Quadratic residual greater than 0.006 | 5,504 |
| Rise or fall at most 0.008 | 1,004 |
| No interior apex | 580 |
| Duration outside 0.2–3 seconds | 442 |
| Fewer than nine observations | 286 |
| Accepted | 140 |
| Total | 15,171 |

These segments include floor motion, jitter and association errors. The 0.92% acceptance rate is NOT airborne recall; no labeled airborne ground truth was evaluated. The classifier requires a complete ascent/apex/descent, which is stronger than requiring curved flight. It fits an entire candidate segment; an otherwise good flight contaminated by stationary or misassociated observations can fail. Fixed normalized thresholds are not perspective/ball-size calibrated.

## Rendering verification

Live QM30 renderer with airborne filter: 7.51s → 1 circle; 20s → 2; 60s → 0; 95s → 1; 120s → 0. The renderer does display accepted classified tracks. Of 140 accepted arcs, only two contain no 2-Hz overlay sample; median accepted duration is 1.018 seconds. Sampling is a secondary loss, not the cause of zero flights in the auto-v1 reports.

## Recommended fixes

1. Represent missing track evidence separately from an empty accepted set; show classification availability and report version.
2. For airborne filtering, accept sufficiently observed, consistently curved partial arcs without requiring a visible apex, while retaining stricter scoring evidence requirements.
3. Segment launch/flight/landing more carefully and scale fit tolerances by apparent ball size; validate changes on labeled visible flights before calling them accuracy improvements.
4. Use flight timestamps for playback and render short accepted flights independently of 2-Hz detection snapshots.
