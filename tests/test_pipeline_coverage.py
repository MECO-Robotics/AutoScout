"""Exercise cutoff reporting and archives through the real pipeline with fake inference."""
import gzip
import json
import sys
import pytest
from types import SimpleNamespace
import cv2
import numpy as np
from autoscout.store import Store
from autoscout.automatic import run


@pytest.mark.parametrize('begin',[0,1])
@pytest.mark.parametrize('tail_failure',[False,True])
def test_cutoff_retains_tail_score_updates_and_marks_skipped_frames(tmp_path,monkeypatch,tail_failure,begin):
    store=Store(tmp_path)
    path=tmp_path/'videos/clip.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),6,(320,180))
    for _ in range(60):writer.write(np.zeros((180,320,3),dtype=np.uint8))
    writer.release()
    for name in ('frc9550/model.pt','robots/robottracking.pt'):
        model=tmp_path/'models'/name;model.parent.mkdir(parents=True,exist_ok=True);model.write_bytes(b'fake model')
    match={'key':'2026test_qm1','event_key':'2026test','event_start':'2026-01-01','comp_level':'qm','set_number':1,'match_number':1,'local_video':'videos/clip.avi','alliances':{'blue':{'teams':[1,2,3]},'red':{'teams':[4,5,6]}}}
    store.put_match(match)
    class Values:
        def cpu(self):return self
        def tolist(self):return []
    calls=[]
    class FakeModel:
        def __init__(self,*args):pass
        def to(self,*args):pass
        def predict(self,*args,**kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(boxes=SimpleNamespace(xyxy=Values(),xyxyn=Values(),conf=Values()))]
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:True,get_device_name=lambda _: 'test'),set_num_threads=lambda _:None))
    monkeypatch.setitem(sys.modules,'ultralytics',SimpleNamespace(YOLO=FakeModel))
    monkeypatch.setitem(sys.modules,'rapidocr',SimpleNamespace(RapidOCR=lambda **_:None,OCRVersion=SimpleNamespace(PPOCRV4=1),ModelType=SimpleNamespace(MOBILE=1)))
    monkeypatch.setattr('autoscout.scoring.scoreboard_read',lambda *a:{'blue':None,'red':None,'texts':[]})
    readings=[{'timestamp':t,'blue':value,'red':0,'texts':[]} for t,value in [(0,0),(.5,0),(8,3),(8.5,3)]]
    monkeypatch.setattr('autoscout.match_window.scan_match_window',lambda *a,**k:({'inference_start':begin,'confirmed_end':2,'inference_end':7,'full_clip':False},readings))
    if tail_failure:
        original_capture=cv2.VideoCapture
        class FailingCapture:
            def __init__(self,*args):self.cap=original_capture(*args);self.index=0
            def get(self,*args):return self.cap.get(*args)
            def read(self):
                if self.index==48:return False,None
                self.index+=1;return self.cap.read()
            def release(self):self.cap.release()
        monkeypatch.setattr(cv2,'VideoCapture',FailingCapture)
        with pytest.raises(ValueError,match='decode failed'):run(store,match['key'])
        state=store.match(match['key'])['automatic']
        assert state['frames_processed']==43-begin*6 and state['frames_decoded']==48
        assert state['status']=='failed'
        return
    report=run(store,match['key'])
    assert report['frames_decoded']==60
    assert report['frames_processed']==43-begin*6 # Includes the frame exactly at buffer end.
    assert report['match_window_analyzed'] and not report['all_frames_analyzed']
    assert report['scoreboard_fuel']['blue']==3 # Score settled after GPU cutoff.
    assert report['reconciliation']['unassigned']['blue']==3
    assert report['inference_ranges']==[[begin*6,42]]
    assert report['skipped_ranges']==([[0,5]] if begin else [])+[[43,59]]
    # One robot and one fuel inference per analyzed frame after the single-crop change.
    assert len(calls)==2*report['frames_processed']
    assert all(call['max_det']>300 for call in calls)
    report_path=store.root/store.match(match['key'])['automatic']['report']
    with gzip.open(report_path.with_name('frames.jsonl.gz'),'rt') as f:frames=[json.loads(line) for line in f]
    assert [f['frame'] for f in frames]==list(range(60))
    assert all(f.get('inference_skipped')=='confirmed_pre_match' for f in frames[:begin*6])
    assert all(f.get('inference_skipped')=='confirmed_post_match' for f in frames[43:])
    overlay=json.loads(report_path.with_name('overlay.json').read_text())
    assert len(overlay['frames'])==60
    assert overlay['frames'][-1]['robots']==[]
