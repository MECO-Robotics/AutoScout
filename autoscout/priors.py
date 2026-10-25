"""Statbotics priors, independent of video-supported scoring.

2026 mapping verified against avgupta456/statbotics revision
 a2cea5553e35693d423400f419bd770cb2143408:
 backend/src/breakdown.py, tba/breakdown.py, models/epa/main.py,
 db/models/match.py. Fuel components contain scored hub points (one per fuel).
 TeamMatch was removed; Match.pre_epas is the pre-match source.
"""
import json
import math
import time
import urllib.request
import urllib.error
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from .store import now

BASE = 'https://api.statbotics.io/v3'
VERSION = 2
FUEL_2026 = {'auto_fuel': 0, 'transition_fuel': 2, 'first_shift_fuel': 3, 'second_shift_fuel': 4, 'endgame_fuel': 5}
SCHEMA_SOURCE = 'https://github.com/avgupta456/statbotics/blob/a2cea5553e35693d423400f419bd770cb2143408/backend/src/breakdown.py'


def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'AutoScout/0.3'}), timeout=4) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def components(raw, year, pre=False):
    if year != 2026:
        return None
    epa = raw if pre else raw.get('epa', {})
    if not isinstance(epa, dict):
        return None
    breakdown = epa if pre else epa.get('breakdown', {})
    if not isinstance(breakdown, dict):
        return None
    values = {name: breakdown.get(f'comp_{index}_epa' if pre else name) for name,index in FUEL_2026.items()}
    # Do not trust a derived sum whose upstream missing components became zero.
    return values if all(finite(v) for v in values.values()) else None


def record(team, match, raw, scope, url, pre=False):
    epa = raw.get('epa', {})
    total = epa if pre else epa.get('total_points') if isinstance(epa, dict) else None
    if isinstance(total, dict):
        total = total.get('mean')
    fuel = components(raw, int(match['key'][:4]), pre)
    return {'team': team, 'total_epa': total if finite(total) else None,
            'fuel_estimate': sum(fuel.values()) if fuel is not None else None,
            'fuel_components': fuel, 'fuel_units': 'scored fuel (hub points)' if fuel is not None else None,
            'allocation': None, 'source': f'Statbotics {scope} EPA', 'url': url,
            'as_of': now(), 'reference_time': match.get('time') if pre else raw.get('time'),
            'retrospective': not pre, 'temporal_basis': 'pre-match' if pre else 'event/season aggregate; may include later matches',
            'schema_source': SCHEMA_SOURCE, 'raw': raw,
            'reason': 'Statistical expectation, not observed shots.' if fuel is not None else 'Compatible fuel components unavailable; EPA points are not ball counts.'}


def team_prior(team, match, match_raw=None):
    year = int(match['key'][:4])
    if isinstance(match_raw, dict) and match_raw.get('key') == match['key']:
        pre_epas = match_raw.get('pre_epas') or {}
        pre = pre_epas.get(str(team)) if isinstance(pre_epas, dict) else None
        if isinstance(pre, dict):
            candidate = record(team, match, pre, 'pre-match', BASE + '/match/' + match['key'], pre=True)
            if candidate['fuel_estimate'] is not None:
                return candidate
        else:
            candidate = None
    else:
        candidate = None
    for scope, path in [('event', f'team_event/{team}/{match["event_key"]}'), ('year', f'team_year/{team}/{year}')]:
        url = BASE + '/' + path
        raw = fetch(url)
        if not isinstance(raw, dict) or raw.get('team') != team or raw.get('year', year) != year:
            continue
        if scope == 'event' and raw.get('event', match['event_key']) != match['event_key']:
            continue
        value = record(team, match, raw, scope, url)
        if value['fuel_estimate'] is not None:
            return value
        if candidate is None:
            candidate = value
    return candidate or {'team': team, 'total_epa': None, 'fuel_estimate': None, 'allocation': None,
            'source': 'Statbotics', 'url': BASE + '/match/' + match['key'], 'as_of': now(),
            'reason': 'No available Statbotics record (missing data or service unavailable).'}


def allocate(result, match):
    """Recompute allocation from current official fuel totals, never total score."""
    result = deepcopy(result)
    available = False
    for color, alliance in match['alliances'].items():
        teams = [result['teams'][str(t)] for t in alliance['teams']]
        total = ((match.get('official') or {}).get(color) or {}).get('fuel_points')
        valid = len(teams) == 3 and finite(total) and all(finite(t.get('fuel_estimate')) for t in teams)
        denominator = sum(t['fuel_estimate'] for t in teams) if valid else 0
        for team in teams:
            team['allocation'] = total * team['fuel_estimate'] / denominator if denominator > 0 else None
            team['allocation_source'] = 'TBA alliance fuel × relative Statbotics fuel EPA' if denominator > 0 else None
        available |= denominator > 0
    result['status'] = 'available' if available else 'fuel_prior' if any(v.get('fuel_estimate') is not None for v in result['teams'].values()) else 'epa_only' if any(v.get('total_epa') is not None for v in result['teams'].values()) else 'unavailable'
    return result


def get_priors(store, match):
    key = match['key']
    with store.db() as db:
        row = db.execute('SELECT payload FROM priors WHERE key=?', (key,)).fetchone()
    if row:
        cached = json.loads(row[0])
        if cached.get('version') == VERSION and time.time() - cached['cached_at'] < 3600:
            return allocate(cached, match)
    teams = [t for a in match['alliances'].values() for t in a['teams']]
    match_raw = fetch(BASE + '/match/' + key)
    with ThreadPoolExecutor(max_workers=6) as pool:
        values = list(pool.map(lambda t: team_prior(t, match, match_raw), teams))
    result = {'version': VERSION, 'teams': {str(v['team']): v for v in values}, 'updated_at': now(), 'cached_at': time.time()}
    with store.db() as db:
        db.execute('INSERT OR REPLACE INTO priors VALUES (?,?)', (key, json.dumps(result)))
    return allocate(result, match)
