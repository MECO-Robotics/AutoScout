from pathlib import Path
from fastapi.testclient import TestClient
from autoscout.tba import parse_team_page, parse_match_page
from autoscout.store import Store
from autoscout.app import create_app
from autoscout.metrics import summarize, phase_at

FIXTURES = Path(__file__).parent / 'fixtures'

def sample():
    matches = parse_team_page((FIXTURES/'team.html').read_text(), 8324, 2026)
    return parse_match_page((FIXTURES/'match.html').read_text(), next(m for m in matches if m['key']=='2026flor_qm6'))

def test_real_source_parsing():
    matches = parse_team_page((FIXTURES/'team.html').read_text(), 8324, 2026)
    assert len(matches)==25 and len({m['key'] for m in matches})==25
    m=sample()
    assert m['alliances']['blue']['teams']==[801,5816,8324]
    assert m['official']['blue']['total_points']==141
    assert m['videos'][0]['key']=='MrFg-7jVf8I'
    assert parse_match_page('<html/>',m)['official'] is None

def test_pending_not_scored_and_alignment_required():
    m=sample()
    obs=[dict(team=8324,alliance='blue',kind='fuel_made',count=3,status='pending',timestamp=30)]
    assert summarize(m,obs)['reviewed_makes'] is None
    obs[0]['status']='accepted'
    result=summarize(m,obs)
    assert result['reviewed_makes']==3
    assert all(r['difference'] is None for r in result['comparison'])
    config=dict(timing_confirmed=True,auto_start=0,teleop_start=23)
    result=summarize(m,obs,config)
    assert next(r for r in result['comparison'] if r['alliance']=='blue' and r['phase']=='transition')['reviewed']==3
    assert phase_at(33,config)=='shift1'
    assert phase_at(166,config)=='unmapped'

def test_api_validation_and_review(tmp_path):
    store=Store(tmp_path); m=sample(); store.put_match(m)
    with TestClient(create_app(store)) as c:
        base='/api/matches/'+m['key']
        assert c.get(base).status_code==200
        payload=dict(timestamp=30,team=8324,alliance='red',kind='fuel_made')
        assert c.post(base+'/observations',json=payload).status_code==422
        payload['alliance']='blue';payload['notes']='=HYPERLINK("bad")'
        assert c.post(base+'/observations',json=payload).status_code==200
        assert c.get(base).json()['summary']['reviewed_makes']==1
        assert "'=HYPERLINK" in c.get('/api/export?format=csv').text
        assert c.post(base+'/observations',json=payload,headers={'Origin':'https://other.example'}).status_code==403
        assert c.get(base+'/video').status_code==404
        assert c.get('/api/matches/missing').status_code==404
        assert c.post(base+'/upload',files={'file':('bad.mp4',b'bad','video/mp4')}).status_code==422

def test_removed_manual_detector_endpoints(tmp_path):
    store=Store(tmp_path);m=sample();store.put_match(m)
    with TestClient(create_app(store)) as c:
        base='/api/matches/'+m['key']
        assert c.put(base+'/config',json={}).status_code==404
        assert c.post(base+'/analyze',json={}).status_code==404


def test_video_range_playback(tmp_path):
    store=Store(tmp_path);m=sample()
    path=store.root/'videos'/'sample.mp4';path.write_bytes(bytes(range(256))*4)
    m['local_video']='videos/sample.mp4';store.put_match(m)
    with TestClient(create_app(store)) as c:
        response=c.get('/api/matches/'+m['key']+'/video',headers={'Range':'bytes=0-99'})
        assert response.status_code==206 and len(response.content)==100
