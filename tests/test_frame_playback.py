import gzip
import json
from autoscout.frame_playback import build_frame_chunks


def test_chunks_preserve_each_archived_frame_and_skip_reason(tmp_path):
    folder=tmp_path/'run';folder.mkdir()
    (folder/'overlay.json').write_text(json.dumps({'frames':[],'sample_fps':2}))
    (folder/'report.json').write_text(json.dumps({'frame_rate':3}))
    with gzip.open(folder/'frames.jsonl.gz','wt') as out:
        for i in range(8):
            box=[.1+i*.01,.2,.2+i*.01,.3]
            out.write(json.dumps({'frame':i,'timestamp':i/3,'fuel_boxes':[box],'confidence':[.9],
              'ball_tracks':[{'track_id':7,'box':box}],'inference_skipped':'confirmed_post_match' if i==7 else None})+'\n')
    root=tmp_path/'static';build_frame_chunks(folder,root)
    manifest=json.loads((folder/'overlay.json').read_text())
    assert manifest['archived_frame_count']==8 and len(manifest['frame_chunks'])==2
    frames=[]
    for i in range(2):frames.extend(json.loads((root/'run'/f'{i}.json').read_text())['frames'])
    assert [f['frame'] for f in frames]==list(range(8))
    assert len({f['objects'][0]['box'][0] for f in frames})==8
    assert frames[0]['objects'][0]['track_id']==7
    assert frames[-1]['inference_skipped']=='confirmed_post_match'
