# Initial attribution benchmark scaffold

Created September 10, 2026. No human shot/count labels exist in this manifest. Accuracy targets are not demonstrated. This six-match selection uses completed Orlando reports; Tallahassee and challenging-case selection remain required before cross-event claims. Test splits govern future labeled evaluation, not an assertion that these historical reports have never been inspected.

Run `.venv/bin/python scripts/evaluate-attribution.py --replay` from the project root. The tool reads pinned baseline report paths from `attribution-benchmark.json`, emits JSON to stdout, invokes no GPU detector, and never writes Store or analysis reports. `--latest` selects current reports for comparison. Replay recalculates conservative reconciliation from cached crossings and scoreboard deltas; it does not regenerate trajectories or missing source evidence.

| Match | Split | Capped frames | Source-track crossings | Team-known crossings | Sampled identity coverage | Runtime seconds | Potential tail seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026flor_qm6 | development | 71.4% | 8/38 | 2/38 | 15.0% | 831.8 | 47.9 |
| 2026flor_qm18 | development | 58.8% | 3/18 | 0/18 | 4.5% | 866.4 | 0.0 |
| 2026flor_qm24 | development | 50.3% | 8/48 | 0/48 | 12.2% | 913.7 | 39.0 |
| 2026flor_qm30 | calibration | 64.8% | 45/136 | 1/136 | 3.4% | 992.0 | 0.0 |
| 2026flor_qm42 | test | 66.5% | 8/47 | 3/47 | 16.5% | 946.2 | 0.0 |
| 2026flor_qm50 | test | 64.6% | 32/126 | 5/126 | 10.5% | 944.9 | 0.0 |

Identity coverage counts identified robot detection snapshots divided by all detection snapshots in the sampled history. It is not identity correctness or shooting-time coverage. Source-track crossings do not establish correct shooters. Tail seconds come from end inference on stored OCR, not a measured processing speedup.

## Human evaluation input

Optional `--labels /absolute/path/labels.json` accepts `{"team_counts": [{"match_key": "2026flor_qm6", "team": 8324, "scored_fuel": 10, "complete": true}]}`. The count above illustrates the schema only; it is not an annotation. Supply complete independently reviewed individual totals only; incomplete/off-camera labels should use `complete: false` and are omitted from complete-count scoring. The output reports absolute error and the proposed `max(5, 10% of truth)` threshold; missing predictions fail that threshold and remain unknown. Input labels are not independently verified by the script.

Event precision/recall, shooter accuracy, trajectory coverage, and timing-error evaluation still require human event labels and event matching. Do not substitute TBA alliance totals, statistical priors, or detector outputs for those labels. The `accuracy_demonstrated` field stays false; label ingestion alone is not proof of meeting all acceptance criteria.

## q6 end spot check

Read-only decoded frame inspection at 130.0 seconds showed the Qualification 6 clock at 0:06 and the final 6/6 segment indicator. At 136.5 seconds the main clock showed 0:00; at 141.5 seconds it remained zero and field personnel were beginning to enter the field; at 150 seconds personnel were collecting/resetting fuel. This supports the inferred 136.5-second end as the final match end, rather than autonomous zero, on this clip. The five-second buffer ends at 141.5 seconds. Four sampled frames do not prove that every late ball trajectory is preserved; dense late-action annotation remains pending.
