import gzip
import json
import pytest
from autoscout.playback import add_trails
from autoscout.airborne import observed_arc


def points():
    return [[i/60,.3+.2*i/60,.4-.3*i/60+.3*(i/60)**2] for i in range(61)]


def test_airborne_requires_observed_arc():
    assert observed_arc(points())
    assert observed_arc(points()[:25])
    assert not observed_arc([[t,x,.4+t*.1] for t,x,y in points()])
    assert not observed_arc([[t,x,.4] for t,x,y in points()])
    assert not observed_arc(points()[::15])


def test_complete_flights_link_scoring_and_sampled_objects(tmp_path):
    frames=[]
    for t,x,y in points():
        box=[x-.003,y-.003,x+.003,y+.003]
        frames.append({'timestamp':t,'camera_segment':0,'ball_tracks':[{'track_id':1,'box':box,'velocity':[.2,-.3+.6*t]}]})
    overlay={'frames':[{'timestamp':f['timestamp'],'objects':[{'box':f['ball_tracks'][0]['box']}]} for f in frames[::30]]}
    (tmp_path/'overlay.json').write_text(json.dumps(overlay))
    (tmp_path/'report.json').write_text(json.dumps({'crossings':[{'ball_track':1,'camera_segment':0,'timestamp':.95}]}))
    with gzip.open(tmp_path/'frames.jsonl.gz','wt') as out:
        for frame in frames:out.write(json.dumps(frame)+'\n')
    add_trails(tmp_path)
    result=json.loads((tmp_path/'overlay.json').read_text())
    assert result['trajectory_version']==4
    assert len(result['flights'])==1
    assert result['flights'][0]['scoring']
    assert result['flights'][0]['end']==1
    assert result['frames'][1]['objects'][0]['track_id']==1
    add_trails(tmp_path)
    assert json.loads((tmp_path/'overlay.json').read_text())==result


def test_arc_acceptance_is_invariant_to_image_scale_and_translation():
    original=[p+[.006,.008] for p in points()[:25]]
    assert observed_arc(original)
    transformed=[[t,.1+x*.35,.2+y*.6,w*.35,h*.6] for t,x,y,w,h in original]
    assert observed_arc(transformed)


def test_arc_survives_linear_camera_pan_but_not_straight_motion():
    arc=[[t,x+.05*t,y+.02*t,.006,.006] for t,x,y in points()[:25]]
    assert observed_arc(arc)
    assert not observed_arc([[t,.3+.1*t,.4+.2*t,.006,.006] for t,x,y in points()])


def test_per_frame_score_reads_require_time_confirmation():
    from autoscout.scoring import StableScore
    counter=StableScore(min_confirm_seconds=.25)
    for i in range(10):counter.update(50,i/60)
    assert counter.value is None
    counter.update(50,.3)
    assert counter.value==50


def test_cubic_flight_and_scaled_cubic_flight_are_accepted():
    flight=[[i/60,.2+.15*(i/60)+.12*(i/60)**3,.5-.45*(i/60)+.03*(i/60)**2+.45*(i/60)**3,.006,.006] for i in range(61)]
    assert observed_arc(flight)
    assert observed_arc([[t,.1+x*.4,.2+y*.7,w*.4,h*.7] for t,x,y,w,h in flight])


def test_cubic_does_not_accept_s_curve_or_noisy_line():
    import numpy as np
    curve=[[i/60,.2+.2*i/60,.4+.1*(i/60-.5)**3,.006,.006] for i in range(61)]
    assert not observed_arc(curve)
    rng=np.random.default_rng(3)
    noise=[[i/60,.2+.2*i/60,.4+float(rng.normal(0,.01)),.006,.006] for i in range(61)]
    assert not observed_arc(noise)
