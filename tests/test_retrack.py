import gzip,json
from autoscout.retrack import replay


def test_tracking_replay_consumes_saved_boxes_without_mutating_archive(tmp_path):
    archive=tmp_path/'frames.gz'
    with gzip.open(archive,'wt') as out:
        for i in range(12):out.write(json.dumps({'timestamp':i/60,'fuel_boxes':[[.1,.2,.11,.21]],'robots':[]})+'\n')
    original=archive.read_bytes();r=replay(archive,gap=.2,max_flight=2)
    assert r['frames_replayed']==12 and r['settings']['gap']==.2
    assert archive.read_bytes()==original
