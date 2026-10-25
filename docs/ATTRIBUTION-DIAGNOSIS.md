# Current attribution bottleneck diagnosis

Read-only diagnosis of the latest completed v2 reports for Orlando qualifications 6, 18, 24 and 30, plus direct inspection of q6 footage at 20 and 95 seconds. Runtime pipeline unchanged by this pass.

## Attribution funnel

| Match | Crossing candidates | Linked source track | Known team on crossing | Detection-cap frames |
|---|---:|---:|---:|---:|
| q6 | 77 | 16 | 0 | 70.7% |
| q18 | 66 | 6 | 3 | 29.9% |
| q24 | 37 | 5 | 2 | 14.0% |
| q30 | 68 | 5 | 3 | 51.8% |

These are raw saved-report diagnostics, not correct-shot labels. Across these four runs, 216/248 candidates have no source track, and only 8/248 have a team. Reconciliation can reject or scale those further. The q6 API additionally rejects ten stale source associations from its original validation artifact.

## 1. Hub geometry is wrong before attribution starts

`locate_hubs` in autoscout/scoring.py selects the largest red/blue color contour within a fixed image band and treats a line through that contour as the scoring gate. It does not recognize a hub or its opening.

At q6 95 seconds:

- The inferred red gate spans normalized x 0.7177–0.7667 at y 0.3592. This lies on the red robot at the far right, also detected as robot track 76 with box [0.71693, 0.34258, 0.76617, 0.38072]. The actual red hub is visibly to its left.
- The blue gate spans x 0.2984–0.3432 at y 0.3844, on the blue hub body below its actual opening.
- Over q6, the inferred red gate center ranges from x 0.2464 to 0.7719. In 43/92 samples it lies inside a robot detection. Bounding-box overlap alone is not proof of a wrong gate, but direct frame inspection confirms the failure at 95 seconds.

Consequently, some crossing candidates describe balls crossing a moving robot/colored structure rather than entering a goal. The q6 visual count is 3 blue / 74 red while OCR fuel is 133 blue / 41 red. These are not equivalent measurements, but the imbalance is consistent with a broken goal-event detector.

**Priority:** validate the actual opening geometry and its persistence independently of shot attribution. Reject bumper-like moving contours. Never accept "two colors found" as proof that a camera view is calibrated. The bottom hub views may provide clearer entry evidence, but need separate geometry and event deduplication first.

## 2. Most candidates have no continuous launch-to-entry link

Source matching only considers the first 0.4 seconds of a new moving ball track. If the ball is first detected midway through flight, or its identity changes in a dense cluster, no launch source is recoverable by the current algorithm. It does not reconstruct the flight backward from entry to shooter.

In q6 the four source IDs on crossings are 3, 76, 79 and 87. None is among the 18 track fragments with recognized team identities. Several candidates come from the same track that the hub locator also mistakes for the goal. This is not simply a shortage of OCR readings; the event and identity evidence are associated with different objects/tracks.

**Priority:** after correcting goal geometry, replay cached tracks to inspect launch-to-entry continuity, retain alternatives through ambiguous associations, and connect short tracklets using plausible timing and flight evidence. Evaluate known shooting intervals, rather than total number of robot labels.

## 3. Long-lived floor tracks can masquerade as flights

The initial q6 artifact contains source-to-entry times as long as 14.8 seconds; ten of sixteen source links exceed three seconds. This indicates stale launch inheritance/track association failure, not evidence of a valid flight. Later safeguards reject those links and prevent manual tags from creating scoring credit from them. The safeguards remove bad evidence; they do not recover missing flights.

**Priority:** distinguish airborne trajectories from floor motion and track-ID switches. Gate source association by flight duration and continuity, retaining unknowns when evidence is insufficient.

## 4. Small airborne detections still compete with floor balls

Main-view cropping has not removed crowding: 70.7% of q6 GPU frames still hit the 300-box cap. Other matches vary substantially. Cap rate does not measure recall, but demonstrates that cropping alone did not eliminate the capacity constraint.

**Priority:** compare launch/flight/hub crops or tiles against labeled airborne examples, with duplicate merging. Increasing frame rate alone cannot repair a missed or misassociated ball. Existing pretrained weights remain the constraint; no training is required to investigate crop/association changes.

## What is not the first bottleneck

- GPU throughput: q6 finishes in 15m35s, comfortably within one hour.
- Statbotics: useful as a statistical prior when available, but cannot repair wrong hub geometry or identify a physical shooter.
- Score reconciliation: it cannot infer individual shooters from alliance totals when upstream events have no valid source. Making it assign more would conceal missing evidence.
- More OCR alone: q6 sampled identity coverage improved, but identified tracks never intersected its scoring-source tracks.

## Recommended order

1. Fix and visually validate goal openings on the main view; explicitly reject unsupported geometry.
2. Validate a small set of actual goal-entry events, using bottom views as independent evidence where useful.
3. Diagnose/reconstruct those events backward to launch and robot identity using cached detections.
4. Improve airborne detection coverage where continuity fails; then evaluate OCR/identity recovery on the affected shooters.
5. Reconcile only after the event/source chain is credible.

All counts above are diagnostics. No per-shot precision, recall, or individual score accuracy has been established.
