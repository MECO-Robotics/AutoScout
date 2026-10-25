# Detection, tracking and fit layers

1. Object detection produces frames.jsonl.gz and frame playback chunks. These are retained as source evidence.
2. Review tracking consumes cached boxes and timestamps, independently of YOLO. The UI's Rebuild tracks from detections control runs a separate velocity-assisted, apparent-size-normalized association pass over loaded playback chunks. Max gap and Match radius tune this preview. IDs are local review identities, not saved scoring attribution.
3. Curve fitting consumes track points and computes quadratic/cubic least-squares models over a bounded observed window (up to three seconds). The browser can choose Parabolic, Cubic, or Best fit (lowest RMSE). RMSE is sqrt(mean((dx/box_width)^2+(dy/box_height)^2)), in apparent ball diameters. Require curvature rejects nearly straight fits. The threshold and model can change without inference or archive writes.

All-fuel mode attempts fits for every visible tracked detection, including previously rejected airborne candidates. A quadratic requires at least four observations, a cubic at least five. Gaps and singular fits can prevent a usable model; the status reports detections without usable history. Show rejected fits draws those candidate curves dashed orange; accepted review fits are solid green. These are mathematical candidates over observed time, not confirmed flights or scores. No paths are extrapolated beyond the fitted observation window.

The airborne review filter uses the tunable fit acceptance. Scoring remains based on saved scoring candidates; review tracking does not rewrite scores or training data. Settings currently apply to the open playback session.

## Offline backend replay

`python -m autoscout.retrack 2026flor_qm30 --gap 0.15 --max-flight 3`

This reuses the existing FlightTracker over saved fuel boxes, robot observations, camera segments and hub history. It imports no detector, loads no weights and performs no GPU inference. Results are written separately under data/tracking/<match>/<run>.json, with source-report provenance, configuration and timing. Original reports and detection archives remain unchanged.

Validation: 77 Python tests pass, plus Node regression checks for cubic/quadratic fits, scale invariance, insufficient history, straight-line detection, independent association, gap/camera-cut behavior and immutable input. Desktop/mobile controls were exercised against QM30 at 95 seconds with no JS errors or horizontal overflow; changing RMSE from 0.01 to 10 changed accepted fits from 0/300 to 226/300 using saved tracks. Rebuilding associations generated a separate preview without detector calls.
