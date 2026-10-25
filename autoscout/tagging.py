"""Reviewer identity overlays; generated evidence is never rewritten."""
from copy import deepcopy
from .scoring import reconcile, physical_volleys


def apply_tags(report, tags, match):
    result = deepcopy(report)
    active = [t for t in tags if not t.get('deleted') and t['run_id'] == report['run_id']]
    crossings = result.get('crossings', [])
    affected = 0
    conflicts = []
    incompatible = set()
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if (a['team'] == b['team'] and a.get('track_id') != b.get('track_id')
                    and max(a['start'], b['start']) < min(a['end'], b['end'])
                    and a.get('camera_segment') == b.get('camera_segment')):
                incompatible.update((a['id'], b['id']))
                conflicts.append({'reason': 'Same team tagged to simultaneous different tracks', 'tag_ids': [a['id'], b['id']]})
    rejected_sources=0
    for c in crossings:
        # v2's first validation exposed long-lived floor tracks with stale launches.
        # Retain raw reports, but never let an identity tag turn those into credit.
        if report.get('version')=='auto-v2' and c.get('launch_timestamp') is not None and c['timestamp']-c['launch_timestamp']>3:
            c['source_rejection']='launch older than three-second association window'
            c['robot_track']=None;c['team']=None;rejected_sources+=1
        candidates = [t for t in active if t.get('track_id') is not None
                      and t['track_id'] == c.get('robot_track')
                      and t['start'] <= c.get('launch_timestamp', c['timestamp']) <= t['end']
                      and (t.get('camera_segment') is None or t['camera_segment'] == c.get('camera_segment'))]
        teams = {t['team'] for t in candidates}
        if len(teams) > 1 or any(t['id'] in incompatible for t in candidates):
            c['team'] = None
            conflicts.append({'timestamp': c['timestamp'], 'track_id': c.get('robot_track'), 'tag_ids': [t['id'] for t in candidates]})
        elif teams:
            team = next(iter(teams))
            c['team'] = team if team in match['alliances'][c['alliance']]['teams'] else None
            c['identity_source'] = 'reviewer tag'
            affected += 1
    if active or rejected_sources:
        roster = [t for a in match['alliances'].values() for t in a['teams']]
        result['reconciliation'] = reconcile(report.get('reconciliation', {}).get('volleys', []), crossings, roster)
        if 'physical_volleys' in report:result['physical_volleys']=physical_volleys(crossings)
    result['manual_tags'] = active
    result['tag_review'] = {'affected_crossings': affected, 'rejected_stale_sources':rejected_sources, 'conflicts': conflicts,
                            'pending': [t['id'] for t in active if t.get('track_id') is None],
                            'note': 'Identity corrections affect cached linked crossings only; drawn boxes require trajectory reconstruction.'}
    return result
