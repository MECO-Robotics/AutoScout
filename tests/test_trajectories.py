from collections import Counter

from autoscout.trajectories import FlightTracker


def box(x,y):
    return [x-.003,y-.003,x+.003,y+.003]


def run(engine, robots=None, gap=False, segment=0):
    entries=[]
    for i in range(61):
        t=i/60
        if gap and 25<=i<=28:
            engine.update([],t,robots or [],{},segment)
            continue
        _,hits=engine.update([box(.3+.2*t,.4-.3*t+.4*t*t)],t,robots or [],
                             {'blue':{'left':.4,'right':.6,'y':.45}},segment)
        entries.extend(hits)
    return entries


def test_quadratic_flight_bridges_gap_and_matches_launch_robot():
    tracker=FlightTracker()
    robot=(9,{'box':[.27,.4,.33,.44],'votes':Counter({8324:4})})
    hits=run(tracker,[robot],gap=True)
    assert len(hits)==1
    assert hits[0]['team']==8324
    assert hits[0]['robot_track']==9
    assert hits[0]['flight_seconds']<1.1
    assert hits[0]['trajectory']['fit_residual']<.001
    assert hits[0]['trajectory']['full_flight_residual']<.001
    assert len(hits[0]['trajectory']['points'])==hits[0]['trajectory']['samples']


def test_overlapping_launch_robots_remain_unknown():
    robots=[(tid,{'box':[.27,.4,.33,.44],'votes':Counter({team:4})}) for tid,team in [(1,8324),(2,955)]]
    hits=run(FlightTracker(),robots)
    assert len(hits)==1
    assert hits[0]['robot_track'] is None
    assert hits[0]['team'] is None


def test_stationary_floor_ball_never_becomes_flight():
    tracker=FlightTracker()
    for i in range(100):
        tracks,hits=tracker.update([box(.3,.5)],i/60,[],{'blue':{'left':.2,'right':.4,'y':.5}})
        assert not hits
        assert not tracks[0][1]['flight_history']


def test_stale_flight_cannot_relaunch_to_evade_age_limit():
    tracker=FlightTracker(max_flight=.3)
    assert run(tracker)==[]
    assert tracker.diagnostics['stale_flight_rejected']==1


def test_camera_cut_clears_launch_history_and_never_reuses_ids():
    tracker=FlightTracker()
    tracks,_=tracker.update([box(.3,.4)],0,[],{},0)
    old=tracks[0][0]
    tracks,hits=tracker.update([box(.3,.4)],.01,[],{},1)
    assert tracks[0][0]!=old
    assert len(tracker.robots)==1
    assert not hits


def test_source_uses_launch_time_robot_position():
    tracker=FlightTracker()
    hits=[]
    for i in range(61):
        t=i/60
        robot=(9,{'box':[.27+t*.4,.4,.33+t*.4,.44],'votes':Counter({8324:4})})
        _,new=tracker.update([box(.3+.2*t,.4-.3*t+.4*t*t)],t,[robot],{'blue':{'left':.4,'right':.6,'y':.45}})
        hits.extend(new)
    assert hits[0]['team']==8324


def test_stationary_prefix_does_not_age_the_subsequent_flight():
    tracker=FlightTracker()
    for i in range(240):
        tracker.update([box(.3,.4)],i/60,[],{})
    hits=[]
    for i in range(61):
        t=i/60
        _,new=tracker.update([box(.3+.2*t,.4-.3*t+.4*t*t)],4+t,[],{'blue':{'left':.4,'right':.6,'y':.45}})
        hits.extend(new)
    assert len(hits)==1
    assert hits[0]['flight_seconds']<1.2


def test_same_track_cannot_be_counted_twice_on_reentry():
    tracker=FlightTracker()
    assert len(run(tracker))==1
    for i in range(1,61):
        t=1+i/60
        y=.5-.15*(i/60) if i<=30 else .425+.15*((i-30)/60)
        _,hits=tracker.update([box(.5,y)],t,[],{'blue':{'left':.4,'right':.6,'y':.45}})
        assert hits==[]


def test_stale_flight_does_not_extend_end_buffer():
    import numpy as np
    from autoscout.scoring import pending_flight
    track={'scored':False,'stale':True,'time':1,'history':[(1,.4,.3)]*5,
           'velocity':np.array([.2,.2]),'point':np.array([.4,.3]),'source_track':9}
    assert not pending_flight({1:track},{'blue':{'left':.3,'right':.5,'y':.4}},1)
