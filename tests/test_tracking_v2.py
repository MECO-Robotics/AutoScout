from collections import Counter
import numpy as np
from autoscout.scoring import MotionTracks,observe_launch,entry_candidate


def test_appearance_prevents_swapping_nearby_robots():
    tracker=MotionTracks(gap=1,radius=.2)
    a=np.array([1.,0.]);b=np.array([0.,1.])
    first=tracker.update([[.1,.1,.2,.2],[.21,.1,.31,.2]],0,[a,b])
    second=tracker.update([[.19,.1,.29,.2],[.12,.1,.22,.2]],.1,[a,b])
    assert [x[0] for x in first]==[x[0] for x in second]


def test_sideways_launch_requires_repeated_departure_and_keeps_ambiguity():
    robot={'box':[.1,.2,.2,.3]}
    track={'history':[(0,.19,.19),(.02,.21,.19),(.04,.23,.19)],'point':np.array([.23,.19]),'velocity':np.array([.4,0])}
    observe_launch(track,[(1,robot)],.04)
    assert 'source_track' not in track
    observe_launch(track,[(1,robot)],.06)
    assert track['source_track']==1
    ambiguous={**track,'source_votes':Counter()}
    ambiguous.pop('source_track')
    for t in (.04,.06):observe_launch(ambiguous,[(1,robot),(2,robot)],t)
    assert 'source_track' not in ambiguous


def test_entry_rejects_gap_and_upward_motion():
    gate={'left':.4,'right':.6,'y':.4}
    track={'history':[(0,.5,.35),(.02,.5,.37),(.04,.5,.39),(.06,.5,.41)],'velocity':np.array([0,.4]),'scored':False}
    assert entry_candidate(track,gate)
    track['history'][-1]=(.3,.5,.41)
    assert not entry_candidate(track,gate)


def test_volley_groups_do_not_merge_unknown_sources_or_camera_cuts():
    from autoscout.scoring import physical_volleys
    crossings=[{'timestamp':2+i*.1,'launch_timestamp':1+i*.1,'camera_segment':segment,'alliance':'blue','robot_track':source,'ball_track':i,'team':8324 if source else None}
               for i,(segment,source) in enumerate([(0,1),(0,1),(1,1),(1,None),(1,None)])]
    groups=physical_volleys(crossings)
    assert [g['crossing_candidates'] for g in groups]==[2,1,1,1]


def test_pending_flight_does_not_require_known_shooter():
    from autoscout.scoring import pending_flight
    ball={'scored':False,'time':1.,'history':[0]*4,'point':np.array([.5,.3]),'velocity':np.array([.1,.2])}
    hubs={'blue':{'left':.45,'right':.55,'y':.4}}
    assert pending_flight({1:ball},hubs,1.05)
    assert not pending_flight({1:ball},hubs,1.3)
    ball['point']=np.array([.9,.6])
    assert not pending_flight({1:ball},hubs,1.05)
