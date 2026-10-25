"""Publish exact archived frames as bounded playback chunks; no interpolation."""
import gzip
import json
from pathlib import Path


def build_frame_chunks(folder, static_root=None):
    path=folder/'overlay.json';overlay=json.loads(path.read_text())
    if overlay.get('frame_chunks_version')==1:return
    report=json.loads((folder/'report.json').read_text());fps=report['frame_rate']
    root=Path(static_root) if static_root else Path(__file__).parent/'static/playback'
    output=root/folder.name;output.mkdir(parents=True,exist_ok=True)
    chunks=[];batch=[];size=max(1,round(fps*2));count=0
    def flush():
        if not batch:return
        name=f'{len(chunks)}.json';dest=output/name
        temp=dest.with_suffix('.tmp');temp.write_text(json.dumps({'frames':batch},separators=(',',':')));temp.replace(dest)
        chunks.append({'start':batch[0]['timestamp'],'end':batch[-1]['timestamp']+1/fps,'url':f'/static/playback/{folder.name}/{name}'})
        batch.clear()
    with gzip.open(folder/'frames.jsonl.gz','rt') as source:
        for line in source:
            f=json.loads(line);tracks=f.get('ball_tracks',[])
            by_box={tuple(t['box']):t['track_id'] for t in tracks}
            objects=[{'box':[round(v,6) for v in box],'confidence':round(conf,3),'label':'fuel','track_id':by_box.get(tuple(box))}
                     for box,conf in zip(f.get('fuel_boxes',[]),f.get('confidence',[]))]
            batch.append({'frame':f.get('frame',count),'timestamp':f['timestamp'],'objects':objects,'robots':f.get('robots',[]),
                          'camera_segment':f.get('camera_segment',0),'hubs':f.get('hubs'),'inference_skipped':f.get('inference_skipped')})
            count+=1
            if len(batch)>=size:flush()
    flush()
    overlay.update(frame_chunks_version=1,frame_chunks=chunks,source_fps=fps,archived_frame_count=count)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(overlay,separators=(',',':')));temp.replace(path)
