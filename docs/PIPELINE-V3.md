# Automatic pipeline v3

Uses the existing pretrained fuel and robot models; no model training.

- Match start: a stable initial 20-second timer plateau followed by three coherent downward ticks establishes the approximate start. Keep a three-second prebuffer. Ambiguous, missing, repeated or conflicting clocks retain frame zero. Full-video scoreboard OCR continues to capture settled scores.
- Coverage: fuel and robot inference both run on every retained source frame. Two overlapping left/right crops cover the main field (vertical 17–68%, horizontal 0–56% and 44–100%). The lower duplicate camera tiles are excluded. Merged detections map back to original video coordinates.
- Limits: removed the 300-result prediction limit and the YOLO end-to-end head's internal 300-result limit. The ceiling now covers all spatial proposals at the configured 960-pixel input (18,900). Confidence filtering and duplicate suppression still apply.
- Robot association: short 0.2-second expiration, velocity prediction, appearance matching, and distances normalized by apparent robot width/height. This is image-scale compensation, not calibrated field coordinates or metric perspective reconstruction.
- Flight association: short quadratic image-space prediction bridges gaps up to 0.12 seconds at 60 fps. Moving detections establish a flight; stationary prefixes do not consume flight lifetime. A crossing must also pass a quadratic consistency check across the full observed flight and saves its trajectory points. It searches historical robot boxes at the observed launch time. Multiple possible sources remain unknown. Flights older than three seconds are rejected; camera cuts clear histories and each surviving track can generate only one entry.
- Archives: every frame is present, including explicit pre/post-match skips; report frame ranges describe both bounds. Playback overlays remain sampled at approximately 2 Hz. Processing retains the existing 59-minute deadline and reports failure if incomplete.

## Validation

68 passing tests cover countdown confirmation/fallback, both skipped ranges, every-frame detector calls, proposal-limit configuration, crop mapping/deduplication, apparent-size compensation, gap bridging, historical launch association, ambiguity, stale rejection, camera cuts and repeated crossings.

A Quadro P600 benchmark on 120 active QM6 frames ran two crops through both detectors plus fuel tracking in 21.26 seconds, with up to 390 merged fuel detections in a frame. This is a short throughput measurement, not a complete-match runtime guarantee or an accuracy measurement.

## Remaining accuracy limitation

Hub openings are still inferred using experimental color geometry. Earlier QM6 inspection showed false hub locations on robot bumpers. The new trajectories do not repair that localization problem. Ball overlap, blur and camera movement can also fragment or swap tracks. Score reconciliation and more detections are not ground-truth validation of shooter identity. Unknown attribution remains explicit.

Re-evaluating QM6's existing OCR samples did not confirm an initial countdown plateau; its beginning remains included. Other supported clips with confirmed pre-match dead time can skip it automatically.

Cached OCR validation confirmed 3–4.5 seconds of safe opening exclusion in QM18, QM24, QM30, QM42, QM50, QM68 and QM76 (including the retained three-second prebuffer).

Final end-to-end GPU validation used an encoded 6-second QM6 excerpt at 60 fps: all 360 frames processed and archived in 98.52 seconds (13.42 seconds scoreboard scan, 84.34 seconds GPU analysis including identity OCR and archives). Maximum 401 fuel detections/frame, 133,778 detections total, 42 stale-flight rejections. These are repeated object detections, not unique balls or scores. The excerpt produced no crossing candidates. Extrapolating GPU work to QM6's 8,491 retained frames plus its prior 385-second OCR scan suggests approximately 40 minutes; this is not a completed full-match measurement.

The first stream-copy test fixture advertised 1,137 frames but decoded only 901; the pipeline correctly failed and retained partial evidence. The replacement encoded fixture completed, including report and overlay generation.

Playback now draws green fuel motion trails, blue robot movement trails, and gold recorded shot trajectories where available. Existing completed reports were augmented from their frame archives without rerunning ML. The fullscreen button expands the video stage with its canvas; native video-only fullscreen is disabled where supported. Sample selection uses actual timestamps and holds each saved sample until the next one. An overlay status explains missing data or excluded footage. Boxes remain sampled evidence rather than interpolated per-frame detector output. Verified QM30 at 95 seconds on desktop and mobile: six robot boxes, 300 historical fuel boxes, 35 motion trails, no JavaScript errors or horizontal overflow; fullscreen retains the canvas.

Fuel highlight controls now use circles and offer All fuel, Scoring candidates only, and Airborne fuel only. Airborne classification requires at least nine observations over 0.2–3 seconds, no gap over 0.15 seconds, a downward-opening image-space quadratic with residual at most 0.006 normalized image units, an interior apex, and at least 0.008 normalized vertical rise and fall. This deliberately excludes incomplete arcs, straight travel and small jitter. It is an observed image-space arc heuristic, not physical certainty.

Playback format trajectory_version=2 stores complete qualifying observed flights, links sampled detections to track IDs, and marks scoring candidates only when the same track/camera segment has a reported crossing within that flight. The separate Full flight trajectories checkbox displays the entire recorded path, including future portions relative to the current offline playback time. Robot trails have their own toggle. Existing saved archives were rebuilt without GPU inference. QM30 contains 140 qualifying arc fragments and zero linked scoring candidates under these criteria; these are not unique-ball or made-shot counts. Desktop/mobile controls verified with no JS errors or overflow; 70 tests pass.
