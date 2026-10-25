# Existing solutions

Checked 2026-09-09. Dates below are GitHub `pushed_at` values, not release dates or evidence of competition readiness. “Inspected” means public documentation, repository trees, and selected source files; no runtime benchmarks were performed. Pinning information is in [the CSV inventory](repository-inventory.csv).

## Video analysis and robot tracking

| Project | Evidence and capability | Last push | Assessment for AutoScout |
|---|---|---|---|
| [derek-pohl/ai-scouting](https://github.com/derek-pohl/ai-scouting) — Team 334 | Gradio video workflow; manual/automatic modes; fuel analysis; robot statistics | 2026-07-06 | Closest reviewed broadcast-video application; hybrid operation has an author-reported competition use case |
| [FRC-Team-955/2026-StreamScouting](https://github.com/FRC-Team-955/2026-StreamScouting) | Fuel detection, trajectory stitching, scoring and attribution source, robot detector weights | 2026-05-02 | Substantive 2026 scoring prototype; benchmark before adoption |
| [ai4funhobby-oss/RobotTracking](https://github.com/ai4funhobby-oss/RobotTracking) | YOLO/ByteTrack, OCR identity, homography, interactive initialization, training artifacts | 2026-03-02 | Useful identity/trajectory experiment; not demonstrated complete scouting |
| [FelixWidmann/Object_Tracking](https://github.com/FelixWidmann/Object_Tracking) | Five tracker experiments, notebooks, labeled images, result CSVs | 2025-12-09 | Useful comparative tracking material; no validated scoring attribution demonstrated |
| [Prosper-FRC/auto_scout](https://github.com/Prosper-FRC/auto_scout) | Reefscape plan, geometry/rules configuration, motion and tracking scripts | 2025-12-17 | Early prototype; much of the advertised architecture remains a plan |
| [Aj-Mulley/FRCAIScoutingProgram](https://github.com/Aj-Mulley/FRCAIScoutingProgram) | Roboflow/Supervision tracking, bounding-box CSV output, ID postprocessing | 2025-05-08 | MIT-licensed exploratory tracking code; integration defects visible in source |
| [sagi21805/Automated-FRC-Scouting](https://github.com/sagi21805/Automated-FRC-Scouting) | C++/Python field, robot, bumper, tracker components | 2023-11-10 | Historical prototype; inspected tree only, no README in that tree |
| [coreyabrown/FRCVideoScout](https://github.com/coreyabrown/FRCVideoScout) | Color-range and tracking experiments with a sample video | 2022-02-04 | Historical vision experiment; not evidence of a current scoring product |
| [churley862/FRC_auto_scout](https://github.com/churley862/FRC_auto_scout) | Repository contains only a short README | 2024-04-28 | Project description, not an available implementation |

### Team 334: most directly relevant broadcast workflow

The README documents composite-video splitting, camera calibration, SAM/HSV fuel detection, optional OCR and local vision-model labeling, and annotated video and statistics outputs. Modes include human tracing and an OCR-only workflow. The SAM checkpoint must be acquired separately; the checked tree contains nine files and no license file. Do not confuse the separate MIT-licensed Castle app with this repository's unspecified license. [Pinned README](https://github.com/derek-pohl/ai-scouting/blob/97184951f9646f047cb5587f4d0aebac8413a729/README.md)

The authors report that fully automatic robot tracking did not work reliably enough on real broadcasts; their deployed workflow used a person to trace robots and mark shooting. Camera position, overlays, occlusion, and robot identity were central failure modes. The report does not provide a standardized held-out per-robot precision/recall benchmark. [First-person retrospective](https://www.chiefdelphi.com/t/building-ai-assisted-frc-scouting-what-worked-what-failed-and-what-we-learned/522442)

Source inspection found `_apply_ocr_score_correction` at line 2711, called by several processing modes. It constrains makes using positive score-OCR changes and plausible prior attempts. **Inference:** reported score agreement after this operation is reconciliation, not an independent measurement of vision accuracy. Preserve an uncorrected output if evaluating the pipeline. The code is concentrated in one large `app.py`; adapting selected concepts may be easier than adopting the entire application. No stable separately versioned public scouting REST contract was established. [Pinned implementation](https://github.com/derek-pohl/ai-scouting/blob/97184951f9646f047cb5587f4d0aebac8413a729/app.py#L2711)

### Team 955: a concrete fuel-scoring implementation

`main.py` calls `check_parabola_score`, uses `PathStitcher`, attributes detected shots to robot slots, and accumulates total and period counts. The repository includes `robot_detector.py`, `robot_tracker.py`, and a YOLO weight file. Its README supplies a command-line video example and recommends CUDA, with a CPU fallback. Reviewed output paths emphasize visualization and printed counts; a documented production REST API was not found. No license file appears in the inspected tree. [Pinned code](https://github.com/FRC-Team-955/2026-StreamScouting/blob/ce8695ed5613ecaec9cf2367a6b789954a2ff9d3/main.py#L478) · [Setup](https://github.com/FRC-Team-955/2026-StreamScouting/blob/ce8695ed5613ecaec9cf2367a6b789954a2ff9d3/README.md)

Use this to study trajectory recovery, scoring-region geometry, duplicate suppression, and attribution. **Unverified:** cross-event accuracy, simultaneous-shooter reliability, team-number identity quality, unattended livestream operation, and processing speed on our hardware.

### Identity and tracking candidates

**RobotTracking** has a target-number workflow combining OCR voting, tracking, and a top-down map. It requires field/camera setup and a robot selection step. The repository advertises tracking coverage and contains training result artifacts, but these do not establish correct scoring attribution. Its nearest-track fallback deserves identity-switch evaluation. The main script and training assets are more useful than its “robust” wording as evidence. No license file was found. [Pinned tracking script](https://github.com/ai4funhobby-oss/RobotTracking/blob/b1af3ef2811f59c25e3908cc96720707e055e66e/plot_robot_traces_trocr.py)

**Object_Tracking** compares DeepSORT, StrongSORT, OC-SORT, a lightweight MeMOT variant, and ByteTrack. The documented evaluation uses track lifetimes, IDs, and interruptions. Those statistics help compare continuity but cannot alone prove that a persistent ID belongs to the correct team. Colab-specific paths need adaptation. The tree includes data and evaluation notebooks; this pass did not reproduce them or audit train/test overlap. No repository license was identified. [Pinned README](https://github.com/FelixWidmann/Object_Tracking/blob/f12fad2fde8be7581c8b6682929f63272e983b4d/README.md)

**Prosper's auto_scout** is worth reading as a Reefscape design sketch. The ten-file tree contains basic tracking and configuration, not the complete ingest/events/database/API pipeline outlined in its README. Treat schedule and generalization estimates as author plans. [Pinned tree](https://github.com/Prosper-FRC/auto_scout/tree/5bb5a2860b5dd42d0d7b3084a3c210b05094e2ee)

**Aj-Mulley's project** is explicitly MIT-licensed. However, `main.py` calls `CSVBetterer.run()` without the required `directory` argument visible in `CSVBetterer.py`. It also uses placeholder model/video configuration. This is concrete evidence that the sampled entrypoint needs repair before use, not a full code review. Its tracker IDs are not automatically validated team identities. [Caller](https://github.com/Aj-Mulley/FRCAIScoutingProgram/blob/73e4ee7cbfbf647798e17bf7210aae1f04a691cf/main.py) · [Function](https://github.com/Aj-Mulley/FRCAIScoutingProgram/blob/73e4ee7cbfbf647798e17bf7210aae1f04a691cf/CSVBetterer.py)

### Project Vector: relevant field evidence, no verified public code

Team 1148 describes dedicated red-hub, blue-hub, and wide cameras, trained detectors, deterministic make detection, operator calibration/identity mapping, and ambiguous-event review. The author reports roughly **87% alliance-total agreement** over fully processed matches at two events. This is self-reported, is not per-robot accuracy, and excludes unprocessed matches. The disclosure explicitly says formal per-robot precision remains to be measured and the repository is private. No public repository was verified during this search. It is a methodology reference, not currently a confirmed reusable GitHub solution. [Author's technical disclosure](https://www.chiefdelphi.com/t/1148-project-vector-ai-scouting-for-rebuilt/519559)

## Scouting applications and analytics

These solve collection, reporting, or statistical estimation. Their existence does not imply automatic video parsing.

| Project | Useful existing capability | License observed | Fit |
|---|---|---|---|
| [FRC2713/QRScout](https://github.com/FRC2713/QRScout) | Configurable forms, QR export, timers/action tracking, TBA integration; 2026 configuration present | MIT | Manual ground-truth and fallback collection |
| [PWNAGERobotics/ScoutingPASS](https://github.com/PWNAGERobotics/ScoutingPASS) | Offline scouting, QR transfer, season configurations, field-image inputs | GPL v3 license text | Manual scouting baseline and field-location capture |
| [FIRSTTeam102/scoutradioz](https://github.com/FIRSTTeam102/scoutradioz) | Multi-team surveys, assignments, reports, TBA webhook integration | AGPL v3 text with per-file exceptions | Operational scouting/reporting reference |
| [Team334/Castle](https://github.com/Team334/Castle) | Team 334's scouting application; TBA and Nexus configuration | MIT | Natural integration reference alongside Team 334's video work |
| [avgupta456/statbotics](https://github.com/avgupta456/statbotics) | EPA ratings, predictions, REST/Python interfaces | MIT | Statistical baseline, not observed shot-level truth |
| [the-blue-alliance/the-blue-alliance](https://github.com/the-blue-alliance/the-blue-alliance) | Public API implementation, schemas, parsers, example fixtures | MIT | Best source for exact response contracts and season mappings |

License observations describe repository files, not a complete audit of bundled weights, datasets, or dependencies. Several strong vision candidates have no declared repository license; keep that unresolved before copying them into a distributable product. [ScoutingPASS license](https://github.com/PWNAGERobotics/ScoutingPASS/blob/e362d4ce3c9e2d232a0c74ffd8be7a42659fbb4a/LICENSE) · [Scoutradioz license](https://github.com/FIRSTTeam102/scoutradioz/blob/752473bc140838fcb4e5b1828a7929e3f8acc6e0/LICENSE)

## Reuse priorities

1. Evaluate Team 334 and Team 955 on the **same manually labeled broadcast matches** before selecting a base.
2. Compare RobotTracking and Object_Tracking approaches specifically on team identity through occlusion, not just detection counts.
3. Use QRScout, ScoutingPASS, Castle, or an existing team workflow to capture corrections and evaluation labels.
4. Reuse TBA schemas/fixtures for ingestion and validation; keep EPA as a separately labeled estimate.

On-robot targeting/localization frameworks were excluded from the main shortlist: they address a different camera viewpoint and usually do not solve six-robot broadcast identity or scoring attribution.
