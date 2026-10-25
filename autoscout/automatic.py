"""Unattended every-frame inference, OCR reconciliation, and robot tracking."""
import argparse
import gzip
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from .store import Store, now
from .ml import model_path
from .detection import proposal_limit

VERSION='auto-v5-single-crop'


def frame_ranges(indices):
    ranges=[]
    for index in indices:
        if ranges and index==ranges[-1][1]+1:ranges[-1][1]=index
        else:ranges.append([index,index])
    return ranges



def run(store,key,limit_seconds=None):
    from .scoring import MotionTracks,StableScore,scoreboard_read,locate_hubs,team_identity,identity,reconcile,robot_appearance,physical_volleys,pending_flight
    from .match_window import scan_match_window
    from .trajectories import FlightTracker
    from .field_geometry import robot_crops,map_crop_boxes,merge_detections
    import torch
    from ultralytics import YOLO
    from rapidocr import RapidOCR,OCRVersion,ModelType
    if not torch.cuda.is_available():raise ValueError('CUDA unavailable; automatic scouting requires GPU inference.')
    gpu_device=os.environ.get('AUTOSCOUT_GPU_DEVICE','0')
    device_count=getattr(torch.cuda,'device_count',lambda:1)()
    if not gpu_device.isdigit() or int(gpu_device)>=device_count:
        raise ValueError(f'CUDA device {gpu_device!r} is unavailable; found {device_count} device(s).')
    device=f'cuda:{gpu_device}'
    started=time.monotonic();m=store.match(key);path=store.video_path(m)
    if not path:raise ValueError('No recording available')
    torch.set_num_threads(2);cv2.setNumThreads(2)
    fuel=YOLO(str(model_path(store)));fuel.to(device)
    robot_path=store.root/'models/robots/robottracking.pt';robots=YOLO(str(robot_path));robots.to(device)
    fuel_limit=proposal_limit(fuel);robot_limit=proposal_limit(robots)
    ocr=RapidOCR(params={'Det.model_type':ModelType.MOBILE,'Rec.model_type':ModelType.MOBILE,'Det.ocr_version':OCRVersion.PPOCRV4,'Rec.ocr_version':OCRVersion.PPOCRV4,'EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':2})
    cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));w=int(cap.get(3));h=int(cap.get(4))
    if fps<=0:raise ValueError('Invalid video frame rate')
    duration=total/fps
    if limit_seconds:total=min(total,int(limit_seconds*fps))
    run_id=uuid.uuid4().hex;folder=store.root/'automatic'/key/run_id;folder.mkdir(parents=True)
    balls=FlightTracker(gap=max(.12,2/fps));bots=MotionTracks(gap=.2,radius=.09,perspective=True)
    roster=[t for a in m['alliances'].values() for t in a['teams']]
    bot_state=[];crossings=[];deltas=[];scores=[];overlay=[];robot_history=[];identity_votes={};hubs={};previous=None
    counters={c:StableScore(min_confirm_seconds=.25) for c in ('blue','red')};processed=0;counts=0;capped_frames=0;cuts=0;last_progress=-10
    # Inference still runs on every retained frame, but keeping a Python
    # playback object for every frame makes long matches consume tens of GB.
    # Keep a responsive half-second playback index instead.
    playback_stride=max(1,round(fps/2))
    ocr_stride=max(1,round(fps/5))
    status={'report':m.get('automatic',{}).get('report'),'version':VERSION,'status':'running','started_at':now(),'run_id':run_id,'progress':0,'frame_rate':fps,'frames_total':total,'frames_processed':0}
    def update():
        current=store.match(key);current['automatic']=status.copy();store.put_match(current)
    update()
    inference_indices=[];skipped_indices=[];inference_frames=0;camera_segments=[];hub_history=[];stage_times={};window={};last_frame_reading=None
    try:
        prepass_started=time.monotonic()
        def prepass_progress(index):
            nonlocal last_progress
            if time.monotonic()-last_progress>=5:
                status.update(stage='scoreboard_scan',progress=.15*index/total,frames_decoded=index,elapsed_seconds=round(time.monotonic()-started,1));update();last_progress=time.monotonic()
        window,scores=scan_match_window(path,ocr,scoreboard_read,deadline=None,limit_seconds=limit_seconds,progress=prepass_progress)
        stage_times['scoreboard_scan']=round(time.monotonic()-prepass_started,2)
        cached_scores={round(reading['timestamp']*fps):reading for reading in scores};scores=[]
        cutoff=window['inference_end'];original_cutoff=cutoff;begin=window.get('inference_start',0)
        status['stage']='gpu_analysis'
        gpu_started=time.monotonic()
        with gzip.open(folder/'frames.jsonl.gz','wt',compresslevel=3) as archive:
            for index in range(total):
                if index%max(1,round(fps*5))==0:
                    import shutil
                    if shutil.disk_usage(folder).free<100*1024**2:raise RuntimeError('Low disk space during analysis; partial evidence retained.')
                ok,frame=cap.read()
                if not ok:raise ValueError(f'Video decode failed at frame {index}; partial evidence retained.')
                timestamp=index/fps
                component_started=time.monotonic()
                reading=cached_scores.get(index)
                if reading is None:
                    if index%ocr_stride==0 or last_frame_reading is None:
                        reading={**scoreboard_read(ocr,frame),'timestamp':timestamp};last_frame_reading=reading
                    else:
                        reading={**last_frame_reading,'timestamp':timestamp}
                stage_times['frame_scoreboard_ocr']=stage_times.get('frame_scoreboard_ocr',0)+time.monotonic()-component_started
                scores.append(reading)
                for alliance,counter in counters.items():
                    event=counter.update(reading[alliance],timestamp)
                    if event:deltas.append({**event,'alliance':alliance,'source':'fuel counter OCR'})
                if timestamp>cutoff and cutoff<total/fps:
                    active=pending_flight(balls.tracks,hubs,timestamp)
                    if active:
                        cutoff=min(total/fps,cutoff+1)
                        if cutoff-original_cutoff>5:
                            cutoff=total/fps;window['reason']='unresolved_late_flight_full_clip'
                        window['inference_end']=cutoff;window['full_clip']=begin==0 and cutoff>=total/fps
                        window['flight_buffer_extended']=True
                if timestamp<begin or timestamp>cutoff:
                    skipped_indices.append(index)
                    skip_reason='confirmed_pre_match' if timestamp<begin else 'confirmed_post_match'
                    overlay_hubs={alliance:{'left':gate['left'],'right':gate['right'],'y':gate['y']} for alliance,gate in hubs.items()}
                    archive.write(json.dumps({'frame':index,'timestamp':timestamp,'inference_skipped':skip_reason,'fuel_boxes':[],'confidence':[],'robots':[],'camera_segment':cuts,'hubs':overlay_hubs})+'\n')
                    if index%playback_stride==0:overlay.append({'frame':index,'timestamp':timestamp,'objects':[],'robots':[],'camera_segment':cuts,'hubs':overlay_hubs,'inference_skipped':skip_reason})
                    processed+=1
                    continue
                inference_frames+=1;inference_indices.append(index)
                thumb=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(64,36));cut=previous is not None and cv2.absdiff(thumb,previous).mean()>28;previous=thumb
                if cut:
                    balls.tracks.clear();bots.tracks.clear();bot_state=[];hubs={};cuts+=1
                    camera_segments.append({'timestamp':timestamp,'segment':cuts,'reason':'visual_change'})
                if True:
                    hubs=locate_hubs(frame)
                    hub_history.append({'timestamp':timestamp,'camera_segment':cuts,'hubs':hubs,'layout':'wide_view_candidate' if len(hubs)==2 else 'uncertain'})
                overlay_hubs={alliance:{'left':gate['left'],'right':gate['right'],'y':gate['y']} for alliance,gate in hubs.items()}
                crops=robot_crops(frame)
                # Serialize the expensive overlay stages: detect balls first,
                # then detect/track robots, then run identity OCR.
                boxes=[];confidence=[];proposal_exhausted=False
                for crop,bounds in crops:
                    pred=fuel.predict(crop,device=device,imgsz=960,conf=.3,verbose=False,max_det=fuel_limit)[0]
                    local_boxes=pred.boxes.xyxyn.cpu().tolist()
                    proposal_exhausted=proposal_exhausted or len(local_boxes)>=fuel_limit
                    boxes.extend(map_crop_boxes(local_boxes,bounds));confidence.extend(pred.boxes.conf.cpu().tolist())
                boxes,confidence=merge_detections(boxes,confidence);counts+=len(boxes)
                capped_frames+=int(proposal_exhausted)
                tracked,entries=balls.update(boxes,timestamp,bot_state,hubs,camera_segment=cuts)
                for crossing in entries:
                    if crossing.get('team') not in m['alliances'][crossing['alliance']]['teams']:crossing['team']=None
                    crossings.append(crossing)
                boxes=[];robot_conf=[]
                for crop,bounds in crops:
                    rr=robots.predict(crop,device=device,imgsz=960,conf=.2,verbose=False,max_det=robot_limit)[0]
                    boxes.extend(map_crop_boxes(rr.boxes.xyxyn.cpu().tolist(),bounds));robot_conf.extend(rr.boxes.conf.cpu().tolist())
                boxes,robot_conf=merge_detections(boxes,robot_conf)
                boxes=[b for b in boxes if .0005<(b[2]-b[0])*(b[3]-b[1])<.035 and b[3]>.25]
                bot_state=bots.update(boxes,timestamp,[robot_appearance(frame,b) for b in boxes])
                component_started=time.monotonic()
                if index%ocr_stride==0:
                    for tid,track in bot_state:
                        team_identity(ocr,frame,track,roster);identity_votes[tid]=track['votes'].copy()
                stage_times['robot_identity_ocr']=stage_times.get('robot_identity_ocr',0)+time.monotonic()-component_started
                robot_objects=[{'track_id':tid,'camera_segment':cuts,'team':identity(t),'box':[round(x,5) for x in t['box']],'position':[round(float(x),5) for x in t['point']]} for tid,t in bot_state]
                archive.write(json.dumps({'frame':index,'timestamp':timestamp,'fuel_boxes':boxes,'confidence':confidence,'robots':robot_objects,'camera_segment':cuts,'camera_cut':bool(cut),'hubs':overlay_hubs,'ball_tracks':[{'track_id':tid,'box':t['box'],'velocity':t['velocity'].tolist(),'source_track':t.get('source_track'),'stale':t.get('stale',False),'scored':t['scored'],'flight_start':t['flight_history'][0][0] if t.get('flight_history') else None,'fit_residual':t['fit'][1] if t.get('fit') is not None else None} for tid,t in tracked]},separators=(',',':'))+'\n')
                if index%playback_stride==0:
                    overlay.append({'timestamp':timestamp,'objects':[{'box':b,'confidence':c,'label':'fuel'} for b,c in zip(boxes,confidence)],'robots':robot_objects,'camera_segment':cuts,'hubs':overlay_hubs})
                    robot_history.append({'timestamp':timestamp,'robots':robot_objects})
                processed+=1
                if time.monotonic()-last_progress>=5:
                    elapsed=time.monotonic()-started;status.update(stage_times={k:round(v,2) for k,v in stage_times.items()},progress=.15+.85*processed/total,frames_processed=inference_frames,frames_decoded=processed,elapsed_seconds=round(elapsed,1),estimated_total_seconds=round(stage_times['scoreboard_scan']+(time.monotonic()-gpu_started)*max(0,min(total,int(cutoff*fps)+1)-int(begin*fps))/max(1,inference_frames),1),scoreboard_fuel={c:v.value for c,v in counters.items()},crossing_candidates=len(crossings),robot_tracks=len(bot_state));update();last_progress=time.monotonic()
        stage_times['gpu_analysis']=round(time.monotonic()-gpu_started,2)
        elapsed=time.monotonic()-started
        for crossing in crossings:
            candidate=identity({'votes':identity_votes.get(crossing.get('robot_track'),{})})
            crossing['team']=candidate if candidate in m['alliances'][crossing['alliance']]['teams'] else None
        reconciliation=reconcile(deltas,crossings,roster)
        report={'version':VERSION,'run_id':run_id,'match_key':key,'status':'complete' if total==round(duration*fps) else 'benchmark','frames_processed':inference_frames,'frames_decoded':processed,'frames_total':total,'frame_rate':fps,'all_frames_analyzed':inference_frames==total,'match_window_analyzed':processed==total,'match_window':window,'inference_ranges':frame_ranges(inference_indices),'skipped_ranges':frame_ranges(skipped_indices),'stage_times':stage_times,'camera_segments':camera_segments,'hub_history':hub_history,'duration':total/fps,'elapsed_seconds':round(elapsed,2),'gpu':torch.cuda.get_device_name(int(gpu_device)),'device':device,'fuel_detections':counts,'capped_frames':capped_frames,'detection_limit':fuel_limit,'robot_detection_fps':fps,'field_crops':1,'trajectory_diagnostics':dict(balls.diagnostics),'scoreboard_fuel':{c:v.value for c,v in counters.items()},'raw_crossing_counts':{c:sum(x['alliance']==c for x in crossings) for c in counters},'reconciliation':reconciliation,'crossings':crossings,'physical_volleys':physical_volleys(crossings),'scoreboard_samples':scores,'robot_history':robot_history,'identified_tracks':{str(tid):identity({'votes':v}) for tid,v in identity_votes.items() if identity({'votes':v}) is not None},'hubs':hubs,'scene_cuts':cuts,'model_hashes':{str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in (model_path(store),robot_path)},'provenance':{'fuel':'frc9550/2026-game-piece','robot':'ai4funhobby-oss/RobotTracking@b1af3ef2811f59c25e3908cc96720707e055e','ocr':'RapidOCR PP-OCRv4 mobile'},'notes':['Experimental shot recognition and robot attribution; unassigned contributions remain explicit.','Scoreboard fuel counters are used, not total score deltas which can include tower and penalty points.','Positions are normalized video coordinates, not field meters.','Every retained match-window frame receives cropped fuel inference; confirmed pre/post-match skips are explicit. Robot and fuel detection run every retained frame in the single full-width main-field crop, with apparent-size compensation for robot association. Accuracy is not yet validated.']}
        report['official_comparison']={c:{'tba_fuel_points':(m.get('official') or {}).get(c,{}).get('fuel_points'),'ocr_fuel':report['scoreboard_fuel'][c]} for c in counters}
        report['elapsed_seconds']=round(time.monotonic()-started,2)
        (folder/'report.json').write_text(json.dumps(report))
        (folder/'overlay.json').write_text(json.dumps({'start':0,'end':total/fps,'sample_fps':fps,'frames':overlay}))
        from .playback import add_trails
        add_trails(folder)
        from .frame_playback import build_frame_chunks
        build_frame_chunks(folder)
        report['elapsed_seconds']=round(time.monotonic()-started,2)
        (folder/'report.json').write_text(json.dumps(report))
        status.update({k:v for k,v in report.items() if k in ('status','frames_processed','frames_total','elapsed_seconds','scoreboard_fuel','raw_crossing_counts','all_frames_analyzed','frames_decoded','match_window_analyzed')},progress=1,report=str((folder/'report.json').relative_to(store.root)),finished_at=now());update()
        return report
    except Exception as exc:
        status.update(status='failed',error=str(exc),stage_times={k:round(v,2) for k,v in stage_times.items()},frames_processed=inference_frames,frames_decoded=processed,elapsed_seconds=round(time.monotonic()-started,2));update();raise
    finally:cap.release()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('key');parser.add_argument('--limit',type=float);args=parser.parse_args()
    r=run(Store(),args.key,args.limit);print(json.dumps({k:r[k] for k in ('status','frames_processed','elapsed_seconds','scoreboard_fuel','raw_crossing_counts')}))
