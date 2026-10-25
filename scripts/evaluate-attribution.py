"""Read-only attribution diagnostics; optional replay and human count evaluation.

Run: .venv/bin/python scripts/evaluate-attribution.py --replay
Optional labels JSON: {"team_counts":[{"match_key":"...","team":8324,
"scored_fuel":10,"complete":true}]}. Only complete, human-verified counts belong
here; never use alliance totals or Statbotics estimates as individual labels.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoscout.match_window import infer_match_window
from autoscout.store import Store


def evaluate(store, manifest, labels=None, replay=False, latest=False):
    result = {'schema_version': 1, 'accuracy_demonstrated': False,
              'limitations': ['Diagnostics are not accuracy metrics.',
                             'Identity coverage is sampled detection coverage, not shooting-time coverage.',
                             'Inferred cutoff savings are footage duration, not measured GPU time saved.',
                             'This initial manifest has one venue; cross-event evaluation remains pending.'],
              'matches': [], 'team_count_evaluation': []}
    reports = {}
    for item in manifest['matches']:
        key = item['match_key']
        match = store.match(key)
        relative = (match.get('automatic', {}).get('report') if match else None) if latest else item.get('baseline_report')
        if not relative:
            result['matches'].append({'match_key': key, 'split': item['split'], 'available': False})
            continue
        report = json.loads((store.root / relative).read_text())
        reports[key] = report
        crossings = report.get('crossings', [])
        snapshots = [r for f in report.get('robot_history', []) for r in f.get('robots', [])]
        known = sum(r.get('team') is not None for r in snapshots)
        window = infer_match_window(report.get('scoreboard_samples', []), report['duration'])
        row = {'match_key': key, 'split': item['split'], 'available': True,
               'run_id': report.get('run_id'), 'version': report.get('version'),
               'status': report.get('status'), 'frames_processed': report['frames_processed'],
               'capped_frame_percent': 100 * report.get('capped_frames', 0) / max(1, report['frames_processed']),
               'crossings': len(crossings),
               'crossings_with_source_track': sum(c.get('robot_track') is not None for c in crossings),
               'crossings_with_team': sum(c.get('team') is not None for c in crossings),
               'robot_detection_snapshots': len(snapshots),
               'identified_detection_snapshots': known,
               'sampled_identity_coverage': known / len(snapshots) if snapshots else None,
               'elapsed_seconds': report['elapsed_seconds'], 'match_window': window,
               'potential_tail_seconds': report['duration'] - window['inference_end']}
        if replay:
            from autoscout.scoring import reconcile
            roster = [t for a in match['alliances'].values() for t in a['teams']]
            row['replayed_reconciliation'] = reconcile(report.get('reconciliation', {}).get('volleys', []), crossings, roster)
        result['matches'].append(row)
    for label in (labels or {}).get('team_counts', []):
        if label.get('complete') is not True:
            continue
        report = reports.get(label['match_key'])
        if not report:
            continue
        counts = report.get('reconciliation', {}).get('team_estimates', {})
        estimate = counts.get(str(label['team']))
        truth = label['scored_fuel']
        if not isinstance(truth, (int, float)) or truth < 0:
            raise ValueError('Human scored_fuel labels must be nonnegative numbers')
        error = abs(estimate - truth) if isinstance(estimate, (int, float)) else None
        result['team_count_evaluation'].append({**label, 'estimate': estimate,
            'absolute_error': error, 'within_proposed_gate': error <= max(5, .1 * truth) if error is not None else False})
    result['human_complete_team_labels'] = len(result['team_count_evaluation'])
    result['label_status'] = 'human_labels_supplied_not_independently_verified' if result['human_complete_team_labels'] else 'no_ground_truth_labels'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/research/attribution-benchmark.json')
    parser.add_argument('--labels', type=Path)
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--latest', action='store_true', help='Compare current Store reports instead of pinned baseline artifacts')
    args = parser.parse_args()
    print(json.dumps(evaluate(Store(), json.loads(args.manifest.read_text()),
          json.loads(args.labels.read_text()) if args.labels else None, args.replay, args.latest), indent=2))
