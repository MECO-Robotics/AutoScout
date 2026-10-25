"""Build lightweight motion trails from archived detections without rerunning ML."""
import gzip
import json
import math
from collections import deque
from .airborne import observed_arc


def add_trails(folder):
    path=folder/'overlay.json'
    data=json.loads(path.read_text())
    if data.get('trajectory_version')==4:return
    frames=iter(data['frames']);target=next(frames,None);histories={};segment=None
    flights=[];active_flights={};has_tracks=False
    report_path=folder/'report.json'
    crossings=json.loads(report_path.read_text()).get('crossings',[]) if report_path.exists() else []
    def finish(key):
        points=active_flights.pop(key,[])
        if not observed_arc(points):return
        scoring=any(c.get('ball_track')==key[1] and c.get('camera_segment',0)==key[0] and points[0][0]<=c['timestamp']<=points[-1][0]+.15 for c in crossings)
        flights.append({'track_id':key[1],'camera_segment':key[0],'start':points[0][0],'end':points[-1][0],'points':points,'scoring':scoring})
    with gzip.open(folder/'frames.jsonl.gz','rt') as source:
        for line in source:
            frame=json.loads(line);t=frame['timestamp']
            if frame.get('camera_cut') or frame.get('camera_segment')!=segment:
                histories.clear();segment=frame.get('camera_segment')
                for key in list(active_flights):finish(key)
            histories={k:v for k,v in histories.items() if t-v[-1][0]<=.15}
            for key,points in list(active_flights.items()):
                if t-points[-1][0]>.15:finish(key)
            active=[]
            has_tracks=has_tracks or bool(frame.get('ball_tracks'))
            for track in frame.get('ball_tracks',[]):
                tid=track['track_id'];b=track['box'];history=histories.setdefault(tid,deque())
                history.append([t,(b[0]+b[2])/2,(b[1]+b[3])/2,b[2]-b[0],b[3]-b[1]])
                while history and t-history[0][0]>.6:history.popleft()
                key=(segment,tid)
                moving=len(history)>=3 and math.hypot(history[-1][1]-history[0][1],history[-1][2]-history[0][2])>.006
                if track.get('stale'):
                    if key in active_flights:finish(key)
                elif key in active_flights:
                    if t-active_flights[key][0][0]>3:finish(key)
                    else:active_flights[key].append(history[-1])
                elif moving:active_flights[key]=list(history)[-9:]
                if len(history)>=3 and not track.get('stale') and math.hypot(*track.get('velocity',[0,0]))>.08:
                    active.append({'track_id':tid,'points':list(history)})
            if target is not None and abs(target['timestamp']-t)<.01:
                target['trails']=[];target['camera_segment']=segment
                tracks=frame.get('ball_tracks',[])
                by_box={tuple(track['box']):track['track_id'] for track in tracks}
                for obj in target.get('objects',[]):obj['track_id']=by_box.get(tuple(obj['box']))
                target=next(frames,None)
    for key in list(active_flights):finish(key)
    data['flights']=flights
    data['trajectory_version']=4
    data['arc_evidence_available']=has_tracks
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,separators=(',',':')));temp.replace(path)
