# FRC AutoScout

Local recorded-video scouting MVP for **team 8324, MECO Robotics, 2026**. Match library, local playback, CUDA YOLO26n fuel detection, optional robot identity tagging, statistical approximations, alliance scoring comparisons, and CSV/JSON exports.

## Run

The current workspace is installed and populated. Open **http://localhost:8324** while the server is running. To restart:

```bash
cd /home/brian/autoscout
.venv/bin/python -m autoscout.cli serve --port 8324
```

For a fresh checkout (Python 3.11+):

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/python -m autoscout.cli sync --team 8324 --year 2026
.venv/bin/python -m autoscout.cli download --all
.venv/bin/python -m autoscout.cli serve
```

Downloading uses yt-dlp, Node for YouTube extraction, and the FFmpeg binary supplied by imageio-ffmpeg. Internet access is needed to sync/download; downloaded footage and review work locally. An optional `TBA_AUTH_KEY` in `.env` enables authenticated API ingestion. Without a key, the app reads public TBA pages and labels that fallback explicitly.

## Included footage

Downloaded all **25 match recordings** listed on [TBA's 2026 team page](https://www.thebluealliance.com/team/8324/2026), checked September 9, 2026: Orlando Regional (12) and Tallahassee Regional (13), about **2.77 GB** of local MP4 files. These are the available linked recordings, not a claim about future events or unpublished footage.

- Files: `data/videos/`
- Match/footage manifests: `data/exports/team-8324-2026.json` and `data/exports/footage-manifest.csv`
- Cached public source pages: `data/sources/`
- Review database: `data/autoscout.sqlite3`
- Evidence: `data/evidence/`

These generated files are ignored by Git. Keep the entire `data/` directory together when backing up.

## Automatic GPU scouting

**Open the dashboard; no analysis button is required.** On server startup, a single background worker picks up downloaded matches and processes them sequentially. Newly downloaded footage is picked up automatically. The dashboard refreshes progress, estimated alliance fuel totals, robot contribution estimates, and explicitly unassigned amounts.

See [automatic pipeline details](docs/AUTOMATIC.md) for evidence semantics, model scheduling, and limits.

Version 2 uses existing pretrained weights only; no training or fine-tuning:

1. A full-clip CPU scoreboard OCR pass establishes clock history and dedicated fuel-counter deltas. A conservative confirmed match end retains a five-second buffer; uncertainty falls back to full-clip detection. OCR still covers the tail.
2. YOLO26n fuel inference on every retained frame, with the main-view band cropped before detection. The crop reduces competition from alternate camera tiles but can still hit the 300-box cap.
3. Robot detection at 6 fps, motion/appearance association, and adaptive roster-constrained number OCR. Positions remain normalized image coordinates and are held between detector updates.
4. Competing launch-source evidence and descending hub-entry candidates, reconciled conservatively with score deltas. Unknown shares stay unassigned. Candidate volley groups are diagnostic, not verified individual scores.
5. Compressed frame evidence, explicit skipped ranges, camera segments, track IDs, source votes, scoreboard history, and sampled playback overlays.

The supervisor enforces a **two-hour wall-clock limit per match**, including the prepass. Timeouts retain partial evidence and remain failures. Full-clip inference (`all_frames_analyzed`) is distinct from complete retained-window coverage (`match_window_analyzed`); intentional post-match skips are explicit. Source edits can still remove gameplay.

The historical **version 1** qualification 6 run finished in **831.77 seconds**, with all **11,367 frames** archived. That measures the old pipeline's throughput, not version 2 accuracy or runtime. Version 2 q6 finished in **935.20 seconds**, decoding 11,367 frames and skipping GPU inference on 2,876 confirmed post-match frames. Automatic team attribution remained unresolved; see [implementation status](docs/IMPLEMENTATION-STATUS.md). See the [historical result](docs/AUTOMATIC.md#verified-full-match-run-historical-version-1).

This workspace has CUDA dependencies and both models installed. For another checkout:

```bash
bash scripts/setup-ml.sh
.venv/bin/python -m autoscout.cli serve
```

Setup installs PyTorch 2.11.0 + CUDA 12.6 for Pascal compatibility and verifies pinned model artifacts. The tested device is a Quadro P600. The fuel model is [frc9550 YOLO26n](https://huggingface.co/frc9550/2026-game-piece); robot detection uses the trained weights in [RobotTracking](https://github.com/ai4funhobby-oss/RobotTracking). Source/license notes are in THIRD_PARTY.md.

Reports and compressed frame evidence live under `data/automatic/<match>/<run>/`; worker logs are in `data/automatic/`. Completed matches at the current pipeline version are skipped on restart; older versions queue for reanalysis and retain their previous report while processing. Interrupted matches resume by restarting their analysis; failed matches remain flagged instead of retrying indefinitely. Keep the app server running for the queue to continue. `AUTOSCOUT_AUTOMATIC=0` disables the background worker for development.

The older sampled detector remains a diagnostic CLI command (`autoscout detect MATCH`); it is not the automatic scoring pipeline. `data/ml/` contains its earlier runs. Its object counts must not be read as made-shot totals.

**Accuracy limits:** Hub geometry is currently tuned to the wide-view 2026 broadcast layout used in this footage. OCR, robot detection, trajectories, and attribution are experimental. The dashboard distinguishes raw crossings, OCR fuel totals, TBA reference values, and unassigned contributions. Matching alliance totals does not prove correct team attribution. No held-out per-robot accuracy claim is made.

## Review a match

Select a match to see one team-contribution table, alliance fuel/unassigned totals, and playback. Video-supported scoring and Statbotics approximations have separate source labels. Statbotics uses compatible 2026 fuel components, prefers pre-match estimates, and marks event/season fallback values retrospective. Missing data remains unavailable; statistical expectations never fill the video's unknown bucket or establish robot identity.

Robot boxes are enabled on playback; fuel boxes toggle independently. Open optional robot tagging, select a visible robot box or track, choose its team and time interval, and save. Edit/undo remain available. The tag can correct identity on cached linked crossings; it cannot create scored balls or repair missing trajectories. Tags are run-specific, so an analysis rerun does not silently transfer them to different tracks. Drawing a missed robot and automatic targeted reconstruction remain pending.

Advanced evidence contains raw diagnostics, manual observations, and exports. The manual hub-crossing detector and its setup controls have been removed. Historical observations and saved timing metadata remain readable.

## What is automated

The automatic workers run trained fuel and robot detectors on CUDA, track positions, read scoreboard fuel counters, and reconcile volley estimates. Configure `AUTOSCOUT_GPU_DEVICES=0,1` to run two video analyses concurrently on a host with two compatible NVIDIA cards; each match is pinned to one GPU and the selected device is recorded in the report. The Meshnet deployment uses this setting on `llmhost`.

Robot identity and scored-shot attribution are now estimated automatically where visual evidence supports them. Misses, cycle time, and defense are not yet automatically reported. The model detects many visible fuel pieces on the current footage, but also produces false positives on some yellow logos and background details. Dense frames can reach the 300-detection cap, reported as `capped_frames`; no measured broadcast precision/recall is claimed.
Official aggregate alliance scores cannot validate individual robot attribution. The app preserves that distinction and does not alter predictions to force a score match. See [MVP implementation notes](docs/MVP.md) and the [research pack](docs/research/README.md) for architecture, existing projects, API coverage, and next work.

The [read-only benchmark scaffold](docs/research/attribution-benchmark.md) pins six completed baseline reports and supports optional human count labels. No labels have been supplied and no per-team accuracy target is established by these diagnostics.

## Checks and commands

```bash
.venv/bin/python -m pytest -q
node --check autoscout/static/app.js
.venv/bin/python -m autoscout.cli download 2026flor_qm6
.venv/bin/python -m autoscout.cli export
.venv/bin/python scripts/evaluate-attribution.py --replay
```

Automated tests cover real public-page parsing, missing data, review isolation, timing, tracking, ML input/path validation, removed-endpoint checks, API validation, and byte-range playback. Desktop/mobile browser captures are in `docs/screenshots/`. The configured service binds to loopback and its Meshnet interface, and has no multi-user authentication; it is a workstation MVP.

## Meshnet access

On this host, open **http://brianlee1731-andes.nord:8324** or **http://100.89.44.45:8324** from an allowed Meshnet peer. The service listens on localhost and this Meshnet IP. Localhost remains available at http://127.0.0.1:8324.

A persistent user service is installed and enabled; user lingering is enabled, so it can run without an open desktop session. It restarts after failures, including waiting for the Meshnet interface to become available.

```bash
systemctl --user status autoscout
systemctl --user restart autoscout
journalctl --user -u autoscout -f
```

The installed service is `~/.config/systemd/user/autoscout.service`; its current configuration is retained in `deploy/autoscout.service`. Update its bind address if this machine's Meshnet IP changes. The CLI supports repeated `--host` arguments for multiple listeners in one app process and one GPU queue.

## Project storage

The complete project, Python environment, downloaded footage, models, database, and analysis artifacts reside on the hard-disk ZFS pool at `/mnt/zfs-storage/All Drives/Brian Data/autoscout`. `/home/brian/autoscout` is a compatibility symlink for existing commands, environment entry points, and workspace links. The user systemd service runs from the hard-disk location. Meshnet remains available at `http://brianlee1731-andes.nord:8324/`.

Moved September 10, 2026: rsync checksum verification found no differences before cutover; SQLite integrity and Meshnet HTTP access passed before removing the old SSD copy.
