"""Replay trajectory tracking from immutable detections, without loading a detector."""
import argparse
from collections import Counter
import gzip
import json
import time
import uuid
from .store import Store
from .trajectories import FlightTracker


def replay(archive, hub_history=(), *, gap=.12, max_flight=3):
    engine=FlightTracker(gap=gap,max_flight=max_flight)
    crossings=[];frames=0;hubs={};history=iter(sorted(hub_history,key=lambda h:h['timestamp']));next_hub=next(history,None)
    with gzip.open(archive,'rt') as source:
        for line in source:
            frame=json.loads(line);timestamp=frame['timestamp'];segment=frame.get('camera_segment',0)
            while next_hub is not None and next_hub['timestamp']<=timestamp:
                hubs=next_hub if next_hub.get('camera_segment',0)==segment else {};next_hub=next(history,None)
            if frame.get('inference_skipped'):continue
            gates=frame.get('hubs') or (hubs.get('hubs',{}) if hubs.get('camera_segment',0)==segment else {})
            robots=[(r['track_id'],{'box':r['box'],'votes':Counter({r['team']:2}) if r.get('team') else Counter()}) for r in frame.get('robots',[])]
            _,entries=engine.update(frame.get('fuel_boxes',[]),timestamp,robots,gates,camera_segment=segment)
            crossings.extend(entries);frames+=1
    return {'frames_replayed':frames,'crossings':crossings,'diagnostics':dict(engine.diagnostics),'settings':{'gap':gap,'max_flight':max_flight}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('match');parser.add_argument('--gap',type=float,default=.12);parser.add_argument('--max-flight',type=float,default=3)
    args=parser.parse_args()
    if not 0<args.gap<=1 or not 0<args.max_flight<=10:parser.error('gap must be in (0,1], max-flight in (0,10]')
    store=Store();match=store.match(args.match);relative=(match or {}).get('automatic',{}).get('report')
    if not relative:parser.error('Match has no saved detection report')
    report_path=store.root/relative;report=json.loads(report_path.read_text());started=time.monotonic()
    result=replay(report_path.with_name('frames.jsonl.gz'),report.get('hub_history',[]),gap=args.gap,max_flight=args.max_flight)
    result.update(source_report=relative,elapsed_seconds=time.monotonic()-started,kind='derived_tracking_review')
    target=store.root/'tracking'/args.match/f'{uuid.uuid4().hex}.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result));print(target)
