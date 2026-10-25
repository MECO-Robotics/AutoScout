import json
from fastapi.testclient import TestClient
from autoscout.app import create_app
from autoscout.store import Store
from autoscout.tagging import apply_tags
from autoscout import priors


def fixture(tmp_path):
    s = Store(tmp_path)
    m = {'key':'2026test_qm1','event_key':'2026test','alliances':{'blue':{'teams':[1,2,3]},'red':{'teams':[4,5,6]}},'automatic':{'run_id':'a','report':'automatic/a/report.json'}}
    r = {'run_id':'a','duration':30,'robot_history':[{'timestamp':5,'robots':[{'track_id':9}]}],
         'crossings':[{'timestamp':8,'launch_timestamp':5,'robot_track':9,'alliance':'blue','team':None}],
         'reconciliation':{'volleys':[{'start':4,'timestamp':9,'delta':10,'alliance':'blue'}]}}
    p=s.root/'automatic/a/report.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(r));s.put_match(m)
    return s,m,r,p


def test_tag_changes_only_linked_evidence_and_undo(tmp_path):
    s,m,r,p=fixture(tmp_path);original=p.read_text()
    c=TestClient(create_app(s))
    body={'run_id':'a','track_id':9,'start':4,'end':6,'team':1}
    response=c.post('/api/matches/2026test_qm1/tags',json=body)
    assert response.status_code==200
    result=c.get('/api/matches/2026test_qm1/automatic').json()['report']
    assert result['reconciliation']['team_estimates']['1']==1
    assert result['reconciliation']['unassigned']['blue']==9
    assert p.read_text()==original
    assert c.delete('/api/matches/2026test_qm1/tags/'+str(response.json()['id'])).status_code==200
    assert c.get('/api/matches/2026test_qm1/automatic').json()['report']['crossings'][0]['team'] is None
    assert c.post('/api/matches/2026test_qm1/tags',json={**body,'run_id':'old'}).status_code==409
    assert c.post('/api/matches/2026test_qm1/tags',json={**body,'team':99}).status_code==422
    with s.db() as db: assert db.execute('SELECT count(*) FROM audit').fetchone()[0]==2


def test_conflicting_tags_and_rerun_do_not_invent_identity(tmp_path):
    s,m,r,p=fixture(tmp_path)
    tags=[{'id':i,'run_id':'a','track_id':9,'start':4,'end':6,'team':i} for i in (1,2)]
    result=apply_tags(r,tags,m)
    assert result['crossings'][0]['team'] is None
    assert result['tag_review']['conflicts']
    r['run_id']='new'
    assert apply_tags(r,tags,m)['manual_tags']==[]


def test_prior_fallback_cache_and_no_point_conversion(tmp_path,monkeypatch):
    s,m,r,p=fixture(tmp_path);calls=[]
    def fetch(url):
        calls.append(url)
        if '/team_year/' in url:
            return {'team':int(url.split('/')[-2]),'epa':{'total_points':{'mean':45},'breakdown':{'fuel':40}}}
    monkeypatch.setattr(priors,'fetch',fetch)
    result=priors.get_priors(s,m)
    assert result['status']=='epa_only'
    assert result['teams']['1']['total_epa']==45
    assert result['teams']['1']['allocation'] is None
    assert result['teams']['1']['retrospective']
    count=len(calls);assert priors.get_priors(s,m)==result;assert len(calls)==count


def test_missing_priors(tmp_path,monkeypatch):
    s,m,r,p=fixture(tmp_path);monkeypatch.setattr(priors,'fetch',lambda url:None)
    assert priors.get_priors(s,m)['status']=='unavailable'


def test_verified_2026_prematch_components_and_allocation(tmp_path,monkeypatch):
    s,m,r,p=fixture(tmp_path)
    m['official']={'blue':{'fuel_points':120,'total_points':180}}
    def fetch(url):
        assert '/match/' in url
        return {'key':m['key'],'pre_epas':{str(t):{'epa':1000,**{f'comp_{i}_epa':t for i in (0,2,3,4,5)}} for t in range(1,7)},'epas':{'1':{'epa':99999}}}
    monkeypatch.setattr(priors,'fetch',fetch)
    result=priors.get_priors(s,m)
    assert result['status']=='available'
    assert result['teams']['1']['fuel_estimate']==5
    assert result['teams']['1']['allocation']==20
    assert result['teams']['2']['allocation']==40
    assert not result['teams']['1']['retrospective']
    assert result['teams']['4']['allocation'] is None
    # Updating official totals must recompute against cached priors.
    m['official']['blue']['fuel_points']=60
    assert priors.get_priors(s,m)['teams']['1']['allocation']==10


def test_missing_or_zero_fuel_never_equal_split(tmp_path):
    s,m,r,p=fixture(tmp_path);m['official']={'blue':{'fuel_points':100}}
    values={str(t):{'fuel_estimate':0,'total_epa':50} for t in range(1,7)}
    assert priors.allocate({'teams':values},m)['teams']['1']['allocation'] is None
    values['1']['fuel_estimate']=5;values['2']['fuel_estimate']=None
    assert priors.allocate({'teams':values},m)['teams']['1']['allocation'] is None
    assert priors.components({'epa':{'breakdown':{'total_fuel':40}}},2026) is None
    assert priors.components({'comp_0_epa':1},2026,True) is None
    assert priors.components({'epa':{'breakdown':{n:1 for n in priors.FUEL_2026}}},2025) is None


def test_edit_cannot_migrate_old_tag_into_new_run(tmp_path):
    s,m,r,p=fixture(tmp_path)
    c=TestClient(create_app(s));body={'run_id':'a','track_id':9,'start':4,'end':6,'team':1}
    tag=c.post('/api/matches/2026test_qm1/tags',json=body).json()
    r['run_id']='b';p.write_text(json.dumps(r));m['automatic']['run_id']='b';s.put_match(m)
    response=c.patch(f'/api/matches/2026test_qm1/tags/{tag["id"]}',json={**body,'run_id':'b','team':2})
    assert response.status_code==409
    assert s.tags(m['key'])[0]['run_id']=='a'
    assert s.tags(m['key'])[0]['team']==1
    # New explicit tag is allowed; old evidence remains scoped to its own run.
    assert c.post('/api/matches/2026test_qm1/tags',json={**body,'run_id':'b'}).status_code==200


def test_tag_cannot_credit_stale_launch_on_long_lived_floor_track():
    from autoscout.tagging import apply_tags
    report={'version':'auto-v2','run_id':'r','crossings':[{'timestamp':20,'launch_timestamp':1,'robot_track':7,'team':None,'alliance':'blue'}],'reconciliation':{'volleys':[{'timestamp':20,'start':18,'alliance':'blue','delta':1}]}}
    tags=[{'id':1,'run_id':'r','track_id':7,'team':8324,'start':0,'end':21}]
    match={'alliances':{'blue':{'teams':[8324,801,5816]},'red':{'teams':[1,2,3]}}}
    result=apply_tags(report,tags,match)
    assert result['crossings'][0]['team'] is None
    assert result['tag_review']['rejected_stale_sources']==1
    assert result['reconciliation']['unassigned']['blue']==1
    assert report['crossings'][0]['robot_track']==7
