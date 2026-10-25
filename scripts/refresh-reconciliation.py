"""Recompute derived reconciliation from retained evidence, without rerunning models."""
import argparse
import gzip
import json
from pathlib import Path
from autoscout.store import Store, now
from autoscout.scoring import reconcile

parser=argparse.ArgumentParser();parser.add_argument('match');args=parser.parse_args();store=Store();m=store.match(args.match)
path=store.root/m['automatic']['report'];r=json.loads(path.read_text())
original=path.with_name('report-original.json')
if not original.exists():original.write_bytes(path.read_bytes())
roster=[t for a in m['alliances'].values() for t in a['teams']]
r['reconciliation']=reconcile(r['reconciliation']['volleys'],r['crossings'],roster)
r['reconciliation_version']='conservative-v2';r['reconciled_at']=now()
count=0;capped=0
with gzip.open(path.with_name('frames.jsonl.gz'),'rt') as frames:
 for line in frames:
  f=json.loads(line);assert f['frame']==count;count+=1;capped+=len(f['fuel_boxes'])>=300
assert count==r['frames_processed']==r['frames_total']
r['archive_verified_frames']=count;r['capped_frames']=capped
part=path.with_name('report.json.part');part.write_text(json.dumps(r));part.replace(path)
overlay_path=path.with_name('overlay.json')
overlay=json.loads(overlay_path.read_text())
for frame in overlay['frames']:
 for obj in frame['objects']:
  if obj.get('track_id')==0:obj.pop('track_id')
overlay_path.write_text(json.dumps(overlay))
print(json.dumps({k:r[k] for k in ('frames_processed','elapsed_seconds','scoreboard_fuel','raw_crossing_counts','identified_tracks','reconciliation','capped_frames')},indent=2))
