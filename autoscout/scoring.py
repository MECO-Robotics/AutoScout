"""Evidence-preserving scoreboard reconciliation and short-term motion tracks."""
from collections import Counter
import re
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


class MotionTracks:
    def __init__(self, gap=.15, radius=.05, perspective=False):
        self.tracks={};self.next_id=1;self.gap=gap;self.radius=radius;self.perspective=perspective

    def update(self, boxes, timestamp, appearances=None):
        self.tracks={i:t for i,t in self.tracks.items() if timestamp-t['time']<=self.gap}
        centers=np.array([[(b[0]+b[2])/2,(b[1]+b[3])/2] for b in boxes])
        keys=list(self.tracks); assigned={}
        if keys and len(centers):
            predictions=np.array([self.tracks[i]['point']+self.tracks[i]['velocity']*min(timestamp-self.tracks[i]['time'],self.gap) for i in keys])
            distances=np.linalg.norm(predictions[:,None]-centers[None,:],axis=2)
            if self.perspective:
                from .field_geometry import perspective_distance
                distances=np.array([[perspective_distance(self.tracks[tid]['box'],box,predictions[a]) for box in boxes] for a,tid in enumerate(keys)])
            radius=1.5 if self.perspective else self.radius
            costs=distances.copy()
            # Reject impossible pairs before assignment so they cannot steal a valid match.
            costs[distances>=radius]=1e6
            if appearances is not None:
                for a,tid in enumerate(keys):
                    old=self.tracks[tid].get('appearance')
                    for b,new in enumerate(appearances):
                        if old is not None and new is not None:
                            similarity=float(np.minimum(old,new).sum())
                            if similarity<.25:costs[a,b]=1e6
                            else:costs[a,b]+=(1-similarity)*radius
            for a,b in zip(*linear_sum_assignment(costs)):
                if costs[a,b]<1e6:assigned[b]=keys[a]
        output=[]
        for j,center in enumerate(centers):
            tid=assigned.get(j)
            if tid is None:
                tid=self.next_id;self.next_id+=1
                self.tracks[tid]={'point':center,'velocity':np.zeros(2),'time':timestamp,'history':[], 'votes':Counter(),'scored':False}
            t=self.tracks[tid];dt=timestamp-t['time']
            if dt>0:t['velocity']=.6*t['velocity']+.4*(center-t['point'])/dt
            if appearances is not None and appearances[j] is not None:
                old=t.get('appearance');new=appearances[j]
                t['appearance']=new if old is None else .8*old+.2*new
            t.update(point=center,time=timestamp,box=boxes[j]);t['history'].append((timestamp,*center));t['history']=t['history'][-90:]
            output.append((tid,t))
        return output


class StableScore:
    """Repeated OCR reads; bounded monotonic updates, corrections retained separately."""
    def __init__(self, min_confirm_seconds=0):self.value=None;self.pending=None;self.repeats=0;self.time=None;self.pending_since=None;self.min_confirm_seconds=min_confirm_seconds
    def update(self,value,timestamp):
        if value is None:return None
        if value!=self.pending:self.pending=value;self.repeats=1;self.pending_since=timestamp;return None
        self.repeats+=1
        if self.repeats<2 or timestamp-self.pending_since<self.min_confirm_seconds:return None
        if self.value is None:self.value=value;self.time=timestamp;return None
        delta=value-self.value
        if delta<=0:return None
        if delta>max(30,40*(timestamp-self.time)):return None
        event={'timestamp':timestamp,'start':self.time,'delta':delta,'before':self.value,'after':value}
        self.value=value;self.time=timestamp
        return event


def scoreboard_read(ocr,frame):
    h,w=frame.shape[:2];out=ocr(frame[:int(h*.17)],use_cls=False)
    result={'blue':None,'red':None,'blue_total':None,'red_total':None,'texts':[]}
    if out.txts is None:return result
    for box,text,confidence in zip(out.boxes,out.txts,out.scores):
        if confidence<.85:continue
        x=float(np.mean(box[:,0]))/w;y=float(np.mean(box[:,1]))/h
        clean=text.replace(' ','');result['texts'].append({'text':text,'confidence':float(confidence),'x':x,'y':y})
        fuel=re.fullmatch(r'(\d{1,4})/(?:100|360)',clean)
        if fuel and (x<.2 or x>.8):result['blue' if x<.2 else 'red']=int(fuel[1])
        if clean.isdigit() and .045<y<.13:
            if .40<x<.46:result['blue_total']=int(clean)
            elif .53<x<.59:result['red_total']=int(clean)
    return result


def locate_hubs(frame):
    """Automatic color geometry for the wide-view 2026 broadcast; reject poor fits."""
    h,w=frame.shape[:2];hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV);out={}
    for color in ('blue','red'):
        if color=='blue':mask=cv2.inRange(hsv,np.array([95,100,45]),np.array([130,255,255]))
        else:mask=cv2.inRange(hsv,np.array([0,80,35]),np.array([14,255,255]))|cv2.inRange(hsv,np.array([150,80,35]),np.array([180,255,255]))
        mask[:int(h*.24)]=0;mask[int(h*.4):]=0;mask[:,:int(w*.2)]=0;mask[:,int(w*.8):]=0
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        candidates=[]
        for contour in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            x,y,bw,bh=cv2.boundingRect(contour);area=cv2.contourArea(contour)
            if .035*w<bw<.085*w and 1.8<bw/max(1,bh)<5 and area>800:
                candidates.append((area,(x/w,(y+.35*bh)/h,(x+bw)/w)))
        if candidates:
            _,(left,y,right)=max(candidates);out[color]={'left':left,'right':right,'y':y,'method':'automatic color geometry','confidence':'experimental'}
    return out


def team_identity(ocr,frame,track,roster):
    h,w=frame.shape[:2];x1,y1,x2,y2=track['box'];x1-=.01;x2+=.01;y1-=.01;y2+=.025
    crop=frame[max(0,int(y1*h)):min(h,int(y2*h)),max(0,int(x1*w)):min(w,int(x2*w))]
    if crop.size==0:return
    if crop.shape[1]<240:crop=cv2.resize(crop,None,fx=2,fy=2)
    result=ocr(crop,use_cls=False)
    if result.txts is None:return
    for text,score in zip(result.txts,result.scores):
        clean=text.strip().upper();normalized=clean.translate(str.maketrans({'B':'8','O':'0','I':'1','S':'5'}))
        threshold=.9 if normalized==clean else .85
        if score>=threshold and normalized.isdigit() and int(normalized) in roster:track['votes'][int(normalized)]+=1


def identity(track):
    votes=track.get('votes',{})
    if not votes:return None
    ordered=sorted(votes.items(),key=lambda x:x[1],reverse=True)
    return ordered[0][0] if ordered[0][1]>=2 and (len(ordered)==1 or ordered[0][1]>=2*ordered[1][1]) else None


def reconcile(deltas,crossings,roster):
    volleys=[];used=set()
    for delta in deltas:
        # Scoreboard lag varies. Preserve mismatches instead of creating trajectories.
        matches=[(i,c) for i,c in enumerate(crossings) if i not in used and c['alliance']==delta['alliance'] and delta['start']-3<=c['timestamp']<=delta['timestamp']+1]
        used.update(i for i,c in matches)
        counts=Counter(c.get('team') for i,c in matches if c.get('team') in roster)
        visual=len(matches);denominator=max(visual,delta['delta'])
        attributed={str(team):round(delta['delta']*n/denominator,2) for team,n in counts.items()} if denominator else {}
        if sum(attributed.values())>delta['delta']:
            largest=max(attributed,key=attributed.get)
            attributed[largest]=round(attributed[largest]-(sum(attributed.values())-delta['delta']),2)
        volleys.append({**delta,'detected_crossings':visual,'difference':visual-delta['delta'],'estimated_team_shares':attributed,
                        'unassigned':max(0,round(delta['delta']-sum(attributed.values()),2)),'method':'scoreboard delta caps identified visual crossings; unseen fuel stays unassigned' if attributed else 'scoreboard delta; attribution unresolved'})
    teams={str(team):round(sum(v['estimated_team_shares'].get(str(team),0) for v in volleys),2) for team in roster}
    return {'volleys':volleys,'team_estimates':{t:n if any(t in v['estimated_team_shares'] for v in volleys) else None for t,n in teams.items()},
            'unmatched_crossings':len(crossings)-len(used),'unassigned':{c:round(sum(v['unassigned'] for v in volleys if v['alliance']==c),2) for c in ('blue','red')}}


def robot_appearance(frame, box):
    """Small normalized HSV histogram; a supporting cue, never team identity."""
    h,w=frame.shape[:2];x1,y1,x2,y2=box
    crop=frame[max(0,int(y1*h)):min(h,int(y2*h)),max(0,int(x1*w)):min(w,int(x2*w))]
    if not crop.size:return None
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    hist=cv2.calcHist([hsv],[0,1],None,[12,4],[0,180,0,256]).ravel()
    return hist/max(float(hist.sum()),1)


def observe_launch(track, robots, timestamp):
    """Accumulate alternative launch sources near the start of a moving track.

    No image-upward assumption. Repeated departure evidence is required; ambiguous
    origins remain unresolved. This is an experimental association, not a made shot.
    """
    history=track['history']
    if len(history)<3 or timestamp-history[0][0]>.4:return
    speed=float(np.linalg.norm(track['velocity']))
    if speed<.08:return
    origin=np.array(history[0][1:]);point=track['point']
    if np.linalg.norm(point-origin)<.008:return
    votes=track.setdefault('source_votes',Counter())
    for tid,robot in robots:
        x1,y1,x2,y2=robot['box'];width=x2-x1;height=y2-y1
        # The detector often finds bumpers; include body space above them.
        if not (x1-.2*width<=origin[0]<=x2+.2*width and y1-max(height*1.5,.035)<=origin[1]<=y2):continue
        center=np.array([(x1+x2)/2,(y1+y2)/2])
        if np.linalg.norm(point-center)<=np.linalg.norm(origin-center):continue
        votes[tid]+=1
    ranked=votes.most_common()
    if ranked and ranked[0][1]>=2 and (len(ranked)==1 or ranked[0][1]>=2*ranked[1][1]):
        track['source_track']=ranked[0][0];track['launch_timestamp']=history[0][0]
    else:
        track.pop('source_track',None);track.pop('launch_timestamp',None)


def entry_candidate(track, gate):
    """Require a descending approach above the gate, rather than one noisy edge."""
    hist=track['history']
    if len(hist)<4 or track['scored']:return False
    t,x,y=hist[-1];previous=hist[-2]
    return (0<t-previous[0]<=.1 and previous[2]<gate['y']<=y
            and gate['left']<=x<=gate['right'] and track['velocity'][1]>.03
            and hist[-3][2]<gate['y'] and y-hist[-3][2]>.001)


def physical_volleys(crossings, gap=1.0):
    """Group same-source flight evidence; never merge unidentified shooters."""
    groups=[];last={}
    for c in sorted(crossings,key=lambda c:c.get('launch_timestamp',c['timestamp'])):
        launch=c.get('launch_timestamp',c['timestamp']);source=c.get('robot_track')
        key=(c.get('camera_segment'),c['alliance'],source)
        current=last.get(key) if source is not None else None
        if current is None or launch-current['last_launch']>gap:
            current={'camera_segment':c.get('camera_segment'),'alliance':c['alliance'],'robot_track':source,'team':c.get('team'),'start':launch,'last_launch':launch,'last_entry':c['timestamp'],'crossing_candidates':0,'ball_tracks':[],'confidence':'experimental'}
            groups.append(current)
            if source is not None:last[key]=current
        current['last_launch']=launch;current['last_entry']=max(current['last_entry'],c['timestamp']);current['crossing_candidates']+=1;current['ball_tracks'].append(c.get('ball_track'))
        if current['team']!=c.get('team'):current['team']=None
    return groups


def pending_flight(tracks, hubs, timestamp):
    """Conservatively keep inference for launch-linked or near-hub moving fuel."""
    for track in tracks.values():
        if track['scored'] or track.get('stale') or timestamp-track['time']>.15 or len(track['history'])<4:continue
        if np.linalg.norm(track['velocity'])<.08:continue
        x,y=track['point']
        near_hub=any(g['left']-.12<=x<=g['right']+.12 and g['y']-.2<=y<=g['y']+.04 for g in hubs.values())
        if track.get('source_track') is not None or near_hub:return True
    return False
