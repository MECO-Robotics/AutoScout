import json
from autoscout.ml import ObjectTracker, read_result
from autoscout.app import MLRequest, create_app
from autoscout.store import Store
from fastapi.testclient import TestClient
import pytest


def test_tracks_reassociate_and_expire():
    t=ObjectTracker()
    assert t.update([[.1,.1,.2,.2]],0)==[1]
    assert t.update([[.11,.11,.21,.21]],.5)==[1]
    assert t.update([[.11,.11,.21,.21]],2)==[2]


def test_ml_request_finite_and_limits():
    for values in ({'sample_fps':0},{'confidence':1},{'start':float('nan')}):
        with pytest.raises(ValueError): MLRequest(**values)


def test_result_path_and_sync_preservation(tmp_path):
    s=Store(tmp_path)
    m={'key':'2026test_qm1','ml_result':'ml/2026test_qm1/run.json','ml_summary':{'device':'cuda:0'}}
    s.put_match(m)
    path=s.root/m['ml_result'];path.parent.mkdir(parents=True);path.write_text(json.dumps({'frames':[]}))
    assert read_result(s,m['key'])=={'frames':[]}
    s.put_match({'key':m['key']})
    assert s.match(m['key'])['ml_summary']['device']=='cuda:0'
    m['ml_result']='../outside.json';s.put_match(m)
    assert read_result(s,m['key']) is None


def test_ml_requires_footage(tmp_path):
    s=Store(tmp_path);s.put_match({'key':'2026test_qm1'})
    with TestClient(create_app(s)) as c:
        assert c.post('/api/matches/2026test_qm1/ml',json={}).status_code==409
        assert c.get('/api/matches/2026test_qm1/ml').json() is None
