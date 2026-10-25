from autoscout.scoring import StableScore,reconcile,MotionTracks,identity
from collections import Counter

def test_ocr_requires_repeated_reading_and_rejects_decrease():
 s=StableScore(); assert s.update(0,0) is None;assert s.update(0,.5) is None
 assert s.update(100,1) is None
 assert s.update(2,1.5) is None
 e=s.update(2,2);assert e['delta']==2
 assert s.update(0,2.5) is None;assert s.update(0,3) is None
 assert s.value==2

def test_reconciliation_conserves_score_delta_with_unassigned():
 d=[dict(alliance='blue',timestamp=5,start=2,delta=6)]
 c=[dict(alliance='blue',timestamp=4,team=8324),dict(alliance='blue',timestamp=4.1,team=None)]
 r=reconcile(d,c,[8324,801,5816]);v=r['volleys'][0]
 assert v['estimated_team_shares']=={'8324':1}
 assert v['unassigned']==5
 assert r['team_estimates']['801'] is None
 assert v['detected_crossings']==2 and v['difference']==-4

def test_total_without_visual_support_is_not_attributed():
 r=reconcile([dict(alliance='red',timestamp=5,start=0,delta=20)],[],[386,3164,7431])
 assert r['unassigned']['red']==20
 assert all(v is None for v in r['team_estimates'].values())

def test_motion_velocity_and_ocr_vote_ambiguity():
 t=MotionTracks(gap=.1,radius=.1)
 a=t.update([[.1,.1,.2,.2]],0)[0]
 b=t.update([[.11,.11,.21,.21]],.016)[0]
 assert a[0]==b[0] and b[1]['velocity'][0]>0
 assert identity({'votes':Counter({8324:1})}) is None
 assert identity({'votes':Counter({8324:2,801:2})}) is None
 assert identity({'votes':Counter({8324:4,801:1})})==8324


def test_fractional_reconciliation_never_overcredits_delta():
 d=[dict(alliance='blue',timestamp=5,start=2,delta=2)]
 c=[dict(alliance='blue',timestamp=4,team=t) for t in (8324,801,5816)]
 v=reconcile(d,c,[8324,801,5816])['volleys'][0]
 assert v['unassigned']>=0
 assert round(sum(v['estimated_team_shares'].values())+v['unassigned'],2)==2
