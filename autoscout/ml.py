"""GPU-only full-frame fuel detection. Detections are objects, never made shots."""
import hashlib
import json
import math
import os
import threading
import time
import uuid
from pathlib import Path

import cv2

GPU_LOCK = threading.Lock()
MODEL_REVISION = 'da2f9c9b3fad702c4b6579a5a4d5d4d4f3fddf42'
MODEL_URL = f'https://huggingface.co/frc9550/2026-game-piece/resolve/{MODEL_REVISION}/model.pt'


def model_path(store):
    return Path(os.environ.get('VISION_YOLO_MODEL', str(store.root/'models/frc9550/model.pt'))).resolve()


def runtime_status(store):
    try:
        import torch
        ready = torch.cuda.is_available()
        devices=os.environ.get('AUTOSCOUT_GPU_DEVICES','0,1').split(',')
        devices=[int(d.strip()) for d in devices if d.strip().isdigit() and int(d.strip()) < torch.cuda.device_count()] if ready else []
        return dict(available=ready and bool(devices) and model_path(store).is_file(), gpu=', '.join(torch.cuda.get_device_name(i) for i in devices) if devices else None,
                    gpus=devices,
                    cuda=torch.version.cuda, torch=torch.__version__, model='frc9550 YOLO26n · fuel',
                    weights_ready=model_path(store).is_file(), error=None if ready else 'CUDA is unavailable. Install a compatible GPU build of PyTorch.')
    except ImportError:
        return dict(available=False, error='Install the ML dependencies and CUDA PyTorch first.', gpu=None)


class ObjectTracker:
    """Conservative nearest-centroid IDs for sampled frames, not robot identities."""
    def __init__(self):
        self.tracks = {}; self.next_id = 1

    def update(self, boxes, timestamp):
        self.tracks = {i:t for i,t in self.tracks.items() if timestamp-t['time'] <= 1}
        centers = [((b[0]+b[2])/2,(b[1]+b[3])/2) for b in boxes]
        pairs = sorted((math.dist(c,t['center']),i,j) for i,t in self.tracks.items() for j,c in enumerate(centers))
        assigned, used = {}, set()
        for distance,i,j in pairs:
            if distance > .045 or i in used or j in assigned: continue
            assigned[j]=i;used.add(i)
        ids=[]
        for j,center in enumerate(centers):
            if j not in assigned:
                assigned[j]=self.next_id;self.next_id+=1
            tid=assigned[j];self.tracks[tid]=dict(center=center,time=timestamp);ids.append(tid)
        return ids


def read_result(store, key):
    match=store.match(key)
    relative=(match or {}).get('ml_result')
    if not relative: return None
    path=(store.root/relative).resolve()
    if not path.is_relative_to(store.root/'ml') or not path.is_file(): return None
    return json.loads(path.read_text())


def run(store, key, start=0., end=None, sample_fps=2., confidence=.25, progress=lambda *_:None):
    if not GPU_LOCK.acquire(blocking=False):
        raise ValueError('The GPU is processing another recording. Wait for that job to finish.')
    cap=None
    try:
        import torch
        from ultralytics import YOLO
        status=runtime_status(store)
        if not status['available']: raise ValueError(status.get('error') or 'Fuel model weights are missing.')
        device=os.environ.get('AUTOSCOUT_GPU_DEVICE','0')
        match=store.match(key)
        path=store.video_path(match) if match else None
        if not path: raise ValueError('Download this recording first.')
        cap=cv2.VideoCapture(str(path))
        fps=cap.get(cv2.CAP_PROP_FPS); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps<=0: raise ValueError('Recording has no usable frame rate.')
        duration=count/fps; end=duration if end is None else min(end,duration)
        if not 0<=start<end or not .5<=sample_fps<=240 or not .01<=confidence<=.99:
            raise ValueError('Invalid detection window, sample rate, or confidence.')
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        step=max(1,round(fps/sample_fps));actual_rate=fps/step
        progress(0,'Loading YOLO26n on CUDA')
        torch.set_num_threads(2)
        torch.cuda.reset_peak_memory_stats()
        model=YOLO(str(model_path(store)))
        model.to(f'cuda:{device}')
        from .detection import proposal_limit
        detection_limit=proposal_limit(model)
        tracker=ObjectTracker(); frames=[]; total=0; previous=None; capped_frames=0
        started=time.monotonic();first=round(start*fps);last=min(count,round(end*fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES,first)
        for index in range(first,last):
            if (index-first)%step:
                if not cap.grab(): raise ValueError(f"Video decode failed at {index/fps:.2f}s; previous result retained.")
                continue
            ok,frame=cap.read()
            if not ok: raise ValueError(f'Video decode failed at {index/fps:.2f}s; previous result retained.')
            thumb=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(64,36))
            cut=previous is not None and cv2.absdiff(thumb,previous).mean()>28
            if cut: tracker.tracks.clear()
            previous=thumb
            # Float32 and batch one fit Pascal GPUs; never silently fall back to CPU.
            prediction=model.predict(frame,device=f'cuda:{device}',imgsz=960,conf=confidence,verbose=False,max_det=detection_limit)[0]
            if prediction.boxes is not None:
                boxes=prediction.boxes.xyxyn.cpu().tolist();scores=prediction.boxes.conf.cpu().tolist()
                classes=prediction.boxes.cls.cpu().tolist()
            else: boxes,scores,classes=[],[],[]
            if len(boxes)>=detection_limit: capped_frames+=1
            ids=tracker.update(boxes,index/fps)
            objects=[dict(box=[round(v,5) for v in box],confidence=round(score,4),label=model.names[int(cls)],track_id=tid)
                     for box,score,cls,tid in zip(boxes,scores,classes,ids)]
            frames.append(dict(timestamp=round(index/fps,4),objects=objects,scene_cut=bool(cut)))
            total+=len(objects)
            progress((index-first+step)/(last-first),f'{index/fps:.0f}/{end:.0f}s · {total} fuel detections · CUDA')
        torch.cuda.synchronize()
        elapsed=time.monotonic()-started
        run_id=uuid.uuid4().hex
        with model_path(store).open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        result=dict(run_id=run_id,match_key=key,model='frc9550/2026-game-piece YOLO26n',model_revision=MODEL_REVISION,
                    model_sha256=digest,model_source=MODEL_URL,device=str(next(model.model.parameters()).device),gpu=status['gpu'],
                    cuda=status['cuda'],torch=status['torch'],peak_vram_mb=round(torch.cuda.max_memory_allocated()/1024**2,1),
                    source_video=match['local_video'],width=width,height=height,start=start,end=end,sample_fps=actual_rate,
                    confidence=confidence,max_detections_per_frame=detection_limit,capped_frames=capped_frames,frames_analyzed=len(frames),object_detections=total,track_fragments=tracker.next_id-1,
                    elapsed_seconds=round(elapsed,2),inference_fps=round(len(frames)/elapsed,2),frames=frames,
                    note='Fuel object detections, not scored fuel or unique balls. Sampled tracks may fragment. No robot identity inferred.')
        folder=store.root/'ml'/key;folder.mkdir(parents=True,exist_ok=True)
        target=folder/f'{run_id}.json';target.write_text(json.dumps(result))
        current=store.match(key)
        current.update(ml_result=str(target.relative_to(store.root)),ml_summary={k:v for k,v in result.items() if k!='frames'})
        store.put_match(current)
        del model
        torch.cuda.empty_cache()
        progress(1,f'{len(frames)} frames analyzed on {status["gpu"]}')
        return current['ml_summary']
    finally:
        if cap: cap.release()
        GPU_LOCK.release()
