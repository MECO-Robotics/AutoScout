const $ = id => document.getElementById(id);
const state = {matches:[], match:null, filter:'pending', limit:30, busy:false};
let overlayRaf = 0;
const video = $('video'), canvas = $('detection-canvas');
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const phaseNames = {auto:'Autonomous',transition:'Transition',shift1:'Shift 1',shift2:'Shift 2',shift3:'Shift 3',shift4:'Shift 4',endgame:'Endgame'};
const actionNames = {fuel_made:'Fuel made',fuel_missed:'Fuel missed',intake:'Intake',ferry:'Ferry',climb_attempt:'Climb attempt',climb_complete:'Climb complete',inactive:'Inactive',note:'Note'};
const timeLabel = n => `${Math.floor(n/60)}:${(n%60).toFixed(1).padStart(4,'0')}`;
state.overlayTime = null;
state.overlayFrame = null;
const hubControls=document.createElement('span');hubControls.className='hub-controls';hubControls.innerHTML='<strong>Hub line</strong> <label>Blue Y <input id="hub-offset-blue" type="number" min="-0.2" max="0.2" step="0.005" value="0"></label> <label>Red Y <input id="hub-offset-red" type="number" min="-0.2" max="0.2" step="0.005" value="0"></label> <label>Padding <input id="hub-padding" type="number" min="0" max="0.2" step="0.005" value="0"></label>';document.querySelector('.playback-tools').prepend(hubControls);
function notice(text, error=false){$('notice').textContent=text;$('notice').classList.toggle('error',error);$('notice').hidden=!text;}
async function api(path, options={}){
 const response=await fetch(path,{...options,headers:options.body instanceof FormData?{}:{'Content-Type':'application/json',...options.headers}});
 if(!response.ok){let data;try{data=await response.json();}catch{throw new Error(`Request failed (${response.status}). Try again.`);}throw new Error(Array.isArray(data.detail)?data.detail.map(e=>e.msg).join(' '):data.detail||'Request failed.');}
 return response.json();
}
function guard(fn){return async(...args)=>{try{await fn(...args);}catch(e){notice(e.message,true);}};}
function focusAlliance(m){return Object.keys(m.alliances).find(c=>m.alliances[c].teams.includes(m.focus_team))||'blue';}
async function loadLibrary(){
 state.matches=await api('/api/matches');
 const selected=$('event-filter').value;
 const events=[...new Map(state.matches.map(m=>[m.event_key,m.event_name])).entries()];
 $('event-filter').innerHTML='<option value="">All events</option>'+events.map(([key,name])=>`<option value="${escapeHtml(key)}">${escapeHtml(name)}</option>`).join('');$('event-filter').value=selected;
 $('library-count').textContent=`${state.matches.length} matches · ${state.matches.filter(m=>m.has_video).length} recordings ready`;
 renderQueue();
}
function renderQueue(){
 const q=$('match-search').value.toLowerCase(),event=$('event-filter').value;
 const matches=state.matches.filter(m=>(!event||m.event_key===event)&&`${m.label} ${m.key} ${m.event_name}`.toLowerCase().includes(q));
 let previous='';
 $('match-list').innerHTML=matches.map(m=>{const group=m.event_key!==previous?`<div class="event-label">${escapeHtml(m.event_name)}</div>`:'';previous=m.event_key;const alliance=focusAlliance(m);
 return group+`<button class="match-item ${state.match?.key===m.key?'active':''}" data-key="${escapeHtml(m.key)}" aria-current="${state.match?.key===m.key?'true':'false'}"><span class="label">${escapeHtml(m.label)}</span><span class="score">${m.alliances.red.score??'–'} : ${m.alliances.blue.score??'–'}</span><small class="${m.has_video?'ready':''}">${m.automatic?.status==='complete'?'Analysis ready':m.automatic?.status==='running'?`Processing ${Math.round((m.automatic.progress||0)*100)}%`:m.automatic?.status==='failed'?'Analysis failed':m.has_video?'Queued for analysis':'Video linked'}</small><span class="alliance ${alliance}">${alliance==='blue'?'Blue':'Red'}</span></button>`;
 }).join('')||'<p class="help" style="padding:16px">No matching matches. Try another filter or sync team data.</p>';
 $('match-list').querySelectorAll('[data-key]').forEach(b=>b.onclick=guard(()=>selectMatch(b.dataset.key)));
}
async function selectMatch(key, preserve=false){
 state.selectionKey=key;state.priors=null;state.tags=[];state.tagEdit=null;state.tagTrack=null;state.autoOverlay=null;state.autoRunId=null;state.ml=null;
 state.overlayFrame=null;state.overlayTime=null;
 const oldTime=video.currentTime||0;
 const m=await api(`/api/matches/${key}`);if(state.selectionKey!==key)return;state.match=m;state.limit=30;
 $('loading').hidden=true;$('match-content').hidden=false;$('match-title').textContent=m.label;$('match-subtitle').textContent=`${m.event_name} · ${m.year}`;
 $('tba-link').href=`https://www.thebluealliance.com/match/${m.key}`;
 $('roster').innerHTML=['blue','red'].map(color=>`<div class="roster-group ${color}"><strong>${color.toUpperCase()}</strong>${m.alliances[color].teams.map(t=>`<span class="${t===m.focus_team?'focus-team':''}">${t}</span>`).join('')}<span>· ${m.alliances[color].score??'–'}</span></div>`).join('');
 const nextSrc=m.has_video?`/api/matches/${m.key}/video`:'';
 if(video.getAttribute('src')!==nextSrc){video.pause();if(nextSrc){video.src=nextSrc;video.poster=`/api/matches/${m.key}/frame?time=5`;}else{video.removeAttribute('src');video.removeAttribute('poster');}video.load();}
 if(preserve&&m.has_video)video.currentTime=oldTime;
 $('video-empty').hidden=m.has_video;$('video').hidden=!m.has_video;
 $('video-status').textContent=m.has_video?`${m.video_metadata?.height||''}p · ${timeLabel(m.video_metadata?.duration||0)} · local`: 'Not downloaded';
 $('download').hidden=m.has_video;$('download').disabled=state.busy;$('youtube-link').hidden=!m.videos.length;if(m.videos.length)$('youtube-link').href=m.videos[0].url;
 $('comparison-alliance').value=focusAlliance(m);
 $('observation-team').innerHTML=['blue','red'].map(color=>`<optgroup label="${color==='blue'?'Blue':'Red'} alliance">${m.alliances[color].teams.map(t=>`<option value="${t}" data-alliance="${color}" ${t===m.focus_team?'selected':''}>${t}${t===m.focus_team?' · focus team':''}</option>`).join('')}</optgroup>`).join('');
 $('source-label').textContent=m.source==='tba_api_v3'?'TBA API v3':'TBA public-page data';
 $('provenance').textContent=`Source: ${m.source==='tba_api_v3'?'TBA API v3':'public TBA match page'} · fetched ${new Date(m.fetched_at).toLocaleDateString()}`;
 const mlResult=await api(`/api/matches/${m.key}/ml`);if(state.selectionKey!==key)return;state.ml=mlResult;renderML();
 await loadAutomatic(m.key);if(state.selectionKey!==key)return;loadTagContext(key).catch(e=>notice(e.message,true));
 renderStats();renderObservations();renderComparison();renderQueue();drawOverlay();updateButtons();
 if(!preserve)history.replaceState(null,'',`/#${m.key}`);
}
function renderStats(){const s=state.match.summary;$('stat-made').textContent=s.reviewed_makes??'Not reviewed';$('stat-missed').textContent=s.reviewed_misses??'Not reviewed';$('stat-accuracy').textContent=s.accuracy===null?'Not reviewed':`${(s.accuracy*100).toFixed(0)}%`;$('stat-tower').textContent=s.tower_outcome??'Unknown';}
function renderComparison(){
 const m=state.match, color=$('comparison-alliance').value;
 $('comparison').innerHTML=m.summary.comparison.filter(r=>r.alliance===color).map(r=>`<tr><td>${phaseNames[r.phase]}</td><td>${r.reviewed??'Unaligned'}</td><td>${r.official??'Unavailable'}</td><td>${r.difference===null?'—':r.difference>0?'+'+r.difference:r.difference}</td></tr>`).join('');
 $('comparison-note').textContent=`${m.official_unit==='count'?'TBA API fuel counts.':'Public TBA displayed fuel values.'} Reviewed counts include all teams on this alliance, not just 8324. A partial review leaves a gap; this is not an accuracy score.`;
}
function renderObservations(){
 const items=state.match.observations.filter(o=>o.status===state.filter);$('review-count').textContent=`${state.match.summary.pending} pending · ${state.match.summary.accepted} accepted`;
 document.querySelectorAll('[data-status]').forEach(b=>{b.classList.toggle('selected',b.dataset.status===state.filter);b.setAttribute('aria-pressed',String(b.dataset.status===state.filter));});
 if(!items.length){$('observations').innerHTML=`<div class="empty-state"><strong>${state.filter==='pending'?'No candidates waiting for review':`No ${state.filter} observations yet`}</strong>${state.filter==='pending'?'Add a reviewed observation while watching.':'Review a candidate or save an observation from the video.'}</div>`;$('load-more').hidden=true;return;}
 $('observations').innerHTML=items.slice(0,state.limit).map(o=>`<article class="observation" data-id="${o.id}"><button class="observation-thumb" data-seek="${o.timestamp}" aria-label="Seek video to ${timeLabel(o.timestamp)}">${o.evidence?`<img src="/${escapeHtml(o.evidence)}" loading="lazy" alt="Candidate at ${timeLabel(o.timestamp)}">`:'<span class="manual-marker">Manual</span>'}</button><div class="observation-text"><strong>${timeLabel(o.timestamp)} · ${o.count} ${escapeHtml(actionNames[o.kind]||o.kind)}</strong><p><span class="${o.alliance}">${o.alliance==='blue'?'Blue':'Red'} alliance</span> · ${o.source==='manual'?'Human observation':o.source==='onnx_gate'?'ONNX proposal':'Color detector proposal'}</p><p>${escapeHtml(o.notes)}</p></div><div class="observation-actions"><select data-team aria-label="Attribute observation ${o.id} to team"><option value="">Unassigned</option>${state.match.alliances[o.alliance].teams.map(t=>`<option value="${t}" ${o.team===t?'selected':''}>${t}</option>`).join('')}</select><button data-review="accepted" class="${o.status==='accepted'?'quiet':'primary'}">${o.status==='accepted'?'Update':'Accept'}</button><button data-review="${o.status==='rejected'?'pending':'rejected'}" class="quiet reject">${o.status==='rejected'?'Restore':'Reject'}</button></div></article>`).join('');
 $('load-more').hidden=items.length<=state.limit;
 $('observations').querySelectorAll('[data-seek]').forEach(b=>b.onclick=()=>{video.currentTime=Math.max(0,Number(b.dataset.seek)-1);video.pause();$('stage').scrollIntoView({behavior:'smooth',block:'center'});});
 $('observations').querySelectorAll('[data-review]').forEach(b=>b.onclick=guard(async()=>{const row=b.closest('[data-id]'),o=state.match.observations.find(x=>x.id===Number(row.dataset.id));const team=row.querySelector('[data-team]').value;b.disabled=true;await api(`/api/observations/${o.id}`,{method:'PATCH',body:JSON.stringify({status:b.dataset.review,team:team?Number(team):null,count:o.count,kind:o.kind,notes:o.notes})});await refresh();}));
}
async function refresh(){await selectMatch(state.match.key,true);await loadLibrary();}
function updateButtons(){for(const id of ['run-ml'])$(id).disabled=state.busy||!state.match?.has_video;$('sync').disabled=state.busy;}
async function followJob(job){
 state.busy=true;updateButtons();$('job').hidden=false;notice('');
 try{while(true){$('job-label').textContent={sync:'Syncing matches',download:'Downloading footage',ml:'Running GPU object detection'}[job.kind]||'Processing';$('job-message').textContent=job.message;$('job-progress').value=job.progress;
 if(job.status==='complete'){notice('Workspace updated.');break;}
 if(job.status==='failed')throw new Error(job.message);
 await new Promise(resolve=>setTimeout(resolve,900));job=await api(`/api/jobs/${job.id}`);}
 }finally{state.busy=false;$('job').hidden=true;updateButtons();await loadLibrary();if(state.match)await selectMatch(state.match.key,true);else if(state.matches.length)await selectMatch(state.matches[0].key);}
}
function drawOverlay(){
 const rect=$('stage').getBoundingClientRect(),ratio=(video.videoWidth||16)/(video.videoHeight||9);
 const width=Math.min(rect.width,rect.height*ratio),height=width/ratio;
 Object.assign(canvas.style,{width:`${width}px`,height:`${height}px`,left:`${(rect.width-width)/2}px`,top:`${(rect.height-height)/2}px`});
 const pixelWidth=Math.round(width*devicePixelRatio),pixelHeight=Math.round(height*devicePixelRatio);
 if(canvas.width!==pixelWidth)canvas.width=pixelWidth;if(canvas.height!==pixelHeight)canvas.height=pixelHeight;
 const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
 drawML(ctx);
}
function point(e){const r=canvas.getBoundingClientRect();return[Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];}
canvas.onpointerdown=e=>selectRobotAt(point(e));
new ResizeObserver(drawOverlay).observe($('stage'));
video.ontimeupdate=()=>{$('video-clock').textContent=timeLabel(video.currentTime);};
video.onseeked=()=>{state.overlayFrame=null;state.overlayTime=null;};
$('back').onclick=()=>video.currentTime=Math.max(0,video.currentTime-2);$('forward').onclick=()=>video.currentTime=Math.min(video.duration||0,video.currentTime+2);$('speed').onchange=()=>video.playbackRate=Number($('speed').value);
$('mark-observation').onclick=()=>$('observation-time').value=video.currentTime.toFixed(1);
$('match-search').oninput=renderQueue;$('event-filter').onchange=renderQueue;$('comparison-alliance').onchange=renderComparison;
document.querySelectorAll('[data-status]').forEach(b=>b.onclick=()=>{state.filter=b.dataset.status;state.limit=30;renderObservations();});
$('load-more').onclick=()=>{state.limit+=30;renderObservations();};
$('sync').onclick=guard(async()=>followJob(await api('/api/sync',{method:'POST',body:JSON.stringify({team:8324,year:2026})})));
$('download').onclick=guard(async()=>followJob(await api(`/api/matches/${state.match.key}/download`,{method:'POST'})));
$('upload').onchange=guard(async()=>{const file=$('upload').files[0];if(!file)return;const form=new FormData();form.append('file',file);notice('Attaching recording…');await api(`/api/matches/${state.match.key}/upload`,{method:'POST',body:form});notice('Recording attached.');await refresh();});
$('observation-form').onsubmit=guard(async e=>{e.preventDefault();const option=$('observation-team').selectedOptions[0];await api(`/api/matches/${state.match.key}/observations`,{method:'POST',body:JSON.stringify({timestamp:Number($('observation-time').value),team:Number(option.value),alliance:option.dataset.alliance,kind:$('observation-kind').value,count:Number($('observation-count').value),notes:$('observation-notes').value})});state.filter='accepted';notice('Reviewed observation saved.');$('observation-notes').value='';await refresh();});
guard(async()=>{const status=await api('/api/status');state.mlRuntime=await api('/api/ml/status');await loadLibrary();const key=location.hash.slice(1);if(state.matches.length)await selectMatch(state.matches.some(m=>m.key===key)?key:state.matches[0].key);else{$('loading').textContent='No matches imported. Sync matches to load the team’s 2026 season.';}if(status.active_jobs.length)await followJob(await api(`/api/jobs/${status.active_jobs[0]}`));})();

function renderML(){
 const r=state.mlRuntime||{},m=state.ml;
 $('ml-device').textContent=r.available?`${r.gpu} · CUDA ${r.cuda} · YOLO26n fuel model`:r.error||'GPU model is unavailable.';
 $('ml-summary').textContent=m?`${m.frames_analyzed} frames analyzed · ${m.object_detections} object detections · ${m.sample_fps.toFixed(1)} sampled fps · ${m.device} · ${m.elapsed_seconds.toFixed(1)}s processing · ${m.start.toFixed(1)}–${m.end.toFixed(1)}s of video${m.capped_frames?` · ${m.capped_frames} frames reached the model proposal limit`:""}`:'GPU analysis runs automatically. Detection overlays appear when processing completes.';
 $('ml-export').hidden=!m;$('ml-export').href=`/api/matches/${state.match.key}/ml`;$('ml-export').download=`${state.match.key}-detections.json`;
 $('ml-jump').hidden=!m?.frames.some(f=>f.objects.length);
}
function playbackFrames(data,t){
 if(!data.frame_chunks)return data.frames;
 const chunks=data.frame_chunks;
 let lo=0,hi=chunks.length;
 while(lo<hi){const mid=(lo+hi)>>1;if(chunks[mid].start<=t)lo=mid+1;else hi=mid;}
 const index=Math.max(0,lo-1);
 const cache=data.chunkCache||(data.chunkCache=new Map());
 const pending=data.chunkPending||(data.chunkPending=new Set());
 for(const n of [index,index+1,index-1,index+2]){
  if(n<0||n>=chunks.length||cache.has(n)||pending.has(n))continue;
  pending.add(n);
  fetch(chunks[n].url).then(r=>{if(!r.ok)throw new Error(`Playback chunk ${r.status}`);return r.json();}).then(result=>{
   cache.set(n,result.frames);data.fitRevision=(data.fitRevision||0)+1;for(const k of cache.keys())if(Math.abs(k-index)>3)cache.delete(k);
   if(state.autoOverlay===data)drawOverlay();
  }).catch(e=>notice(e.message,true)).finally(()=>pending.delete(n));
 }
 if(!cache.has(index))return null;
 return [...(cache.get(index-1)||[]),...cache.get(index),...(cache.get(index+1)||[])];
}

function candidateFits(data,frame,t){
 const rebuilding=$('rebuild-tracks').checked;
 const revision=`${data.fitRevision||0}:${rebuilding}:${$('track-gap').value}:${$('track-distance').value}`;
 if(!data.fitTracks||data.fitTrackRevision!==revision){
  const tracks=new Map();const all=data.frame_chunks?[...data.chunkCache.entries()].sort((a,b)=>a[0]-b[0]).flatMap(e=>e[1]):data.frames;
  for(const f of all)for(const o of f.objects||[]){if(o.track_id==null)continue;const key=`${f.camera_segment??0}:${o.track_id}`;if(!tracks.has(key))tracks.set(key,[]);const b=o.box;tracks.get(key).push([f.timestamp,(b[0]+b[2])/2,(b[1]+b[3])/2,b[2]-b[0],b[3]-b[1]]);}
  const rebuilt=rebuilding?TrajectoryFit.track(all,{gap:Number($('track-gap').value),distance:Number($('track-distance').value)}):null;
  data.fitTracks=rebuilt?.tracks||tracks;data.fitLookup=rebuilt?.lookup;data.fitTrackRevision=revision;data.fitModels=new Map();
 }
 const model=$('trajectory-model').value,limit=Number($('trajectory-rmse').value),paths=[];
 for(const [objectIndex,object] of (frame.objects||[]).entries()){
  if(!rebuilding&&object.track_id==null)continue;
  const key=rebuilding?data.fitLookup.get(`${frame.timestamp}:${objectIndex}`):`${frame.camera_segment??0}:${object.track_id}`,bucket=Math.floor(t/1.5),cacheKey=`${key}:${bucket}:${model}`;
  if(!data.fitModels.has(cacheKey)){
   const points=(data.fitTracks.get(key)||[]).filter(p=>p[0]>=bucket*1.5-.75&&p[0]<=bucket*1.5+2.25);
   const options=(model==='best'?[2,3]:[Number(model)]).map(d=>TrajectoryFit.fit(points,d,Number($('track-gap').value))).filter(Boolean);
   options.sort((a,b)=>a.rmse-b.rmse);data.fitModels.set(cacheKey,options[0]||null);
  }
  const fit=data.fitModels.get(cacheKey);if(fit)paths.push({...fit,track_id:object.track_id,object_index:objectIndex,rejected:fit.rmse>limit||($('trajectory-curvature').checked&&!fit.curved)});
 }
 return paths;
}

function drawML(ctx){
 state.visibleRobots=[];
 if(!(state.autoOverlay||state.ml)){$('overlay-status').textContent=state.automatic?.report?'Loading detections…':'No saved detections yet';return;}
 const data=state.autoOverlay||state.ml;
 const t=typeof state.overlayTime === 'number' ? state.overlayTime : video.currentTime;
 const frames=playbackFrames(data,t);
 if(!frames){$('overlay-status').textContent='Loading this frame’s detections…';return;}
 let lo=0,hi=frames.length;
 while(lo<hi){const mid=(lo+hi)>>1;if(frames[mid].timestamp<t)lo=mid+1;else hi=mid;}
 let i=Math.min(lo,frames.length-1);
 if(i>0&&Math.abs(frames[i-1].timestamp-t)<Math.abs(frames[i].timestamp-t))i--;
 const frame=frames[i];
 const rate=data.frame_chunks?data.source_fps:data.sample_fps;
 if(!frame||Math.abs(frame.timestamp-t)>.55/rate){$('overlay-status').textContent='No detections for this video frame';return;}
 if(frame.inference_skipped){$('overlay-status').textContent='Outside analyzed match window';return;}
 state.overlayFrame=frame.frame??i;
 const mode=$('fuel-filter').value;
 const flights=(data.flights||[]).filter(f=>f.camera_segment===(frame.camera_segment??0)&&frame.timestamp>=f.start&&frame.timestamp<=f.end);
 const selectedFlights=flights.filter(f=>mode!=='scoring'||f.scoring);
 const candidates=candidateFits(data,frame,t);
 const eligible=new Set(mode==='airborne'?candidates.filter(f=>!f.rejected).map(f=>f.object_index):selectedFlights.map(f=>f.track_id));
 const objects=(frame.objects||[]).filter((o,index)=>mode==='all'||eligible.has(mode==='airborne'?index:o.track_id));
 $('overlay-status').textContent=`${frame.robots?.length||0} robot boxes · ${objects.length} fuel circles · ${data.frame_chunks?'1:1 frame sync':`${rate.toFixed(1)} Hz archive`}${(!data.arc_evidence_available&&data.trajectory_version>=3||!data.trajectory_version)&&mode!=='all'?' · arc classification unavailable':''}`;
 {
  const paths=$('fuel-trajectories').checked&&$('ml-overlay').checked?candidates.filter(f=>(mode==='all'||eligible.has(mode==='airborne'?f.object_index:f.track_id))&&(!f.rejected||$('trajectory-rejected').checked)):[];
  $('overlay-status').textContent+=` · ${candidates.filter(f=>!f.rejected).length}/${candidates.length} fits pass · ${(frame.objects||[]).length-candidates.length} without usable history`;
  if($('trajectory-overlay').checked)
  for(const robot of frame.robots||[]){
   const points=[];
   for(let j=Math.max(0,i-Math.ceil(rate*1.5));j<=i;j++){
    const r=(frames[j].robots||[]).find(r=>r.track_id===robot.track_id&&r.camera_segment===robot.camera_segment);
    if(r)points.push([frames[j].timestamp,(r.box[0]+r.box[2])/2,r.box[3]]);
   }
   paths.push({points,robot:true});
  }
 for(const path of paths){
  if(path.points.length<2)continue;
  ctx.beginPath();path.points.forEach((p,j)=>ctx[j?'lineTo':'moveTo'](p[1]*canvas.width,p[2]*canvas.height));
  ctx.setLineDash(path.rejected?[5*devicePixelRatio,4*devicePixelRatio]:[]);ctx.strokeStyle='#101820';ctx.lineWidth=4*devicePixelRatio;ctx.stroke();
  ctx.strokeStyle=path.robot?'#66b5ff':path.rejected?'#ffad66':'#47ff90';ctx.lineWidth=2*devicePixelRatio;ctx.stroke();
 }
 for (const [alliance, gate] of Object.entries(frame.hubs||(state.automatic?.report?.hub_history||[]).findLast(h=>h.timestamp<=t&&h.camera_segment===(frame.camera_segment??0))?.hubs||{})) {
  if(!gate||gate.left==null||gate.right==null||gate.y==null)continue;
  const offset=Number($(`hub-offset-${alliance}`)?.value||0),padding=Number($('hub-padding')?.value||0);
  const y=Math.max(0,Math.min(1,gate.y+offset))*canvas.height;
  const x1=Math.max(0,gate.left-padding)*canvas.width;
  const x2=Math.min(1,gate.right+padding)*canvas.width;
  ctx.setLineDash([6*devicePixelRatio,4*devicePixelRatio]);
  ctx.strokeStyle=alliance==='blue'?'#66b5ff':'#ff8585';
  ctx.lineWidth=3*devicePixelRatio;
  ctx.beginPath();
  ctx.moveTo(x1,y);
  ctx.lineTo(x2,y);
  ctx.stroke();
  ctx.setLineDash([]);
 }
 }
 ctx.setLineDash([]);ctx.lineWidth=2*devicePixelRatio;ctx.font=`${11*devicePixelRatio}px system-ui`;
 for(const [oi,o] of ($("ml-overlay").checked ? objects : []).entries()){const [x1,y1,x2,y2]=o.box;const x=x1*canvas.width,y=y1*canvas.height;
 const radius=Math.max((x2-x1)*canvas.width,(y2-y1)*canvas.height)/2;
 ctx.beginPath();ctx.arc((x1+x2)*canvas.width/2,(y1+y2)*canvas.height/2,radius,0,2*Math.PI);ctx.strokeStyle='#47ff90';ctx.stroke();
 if(oi>=10)continue;
 const label=`${o.label} ${Math.round(o.confidence*100)}%${o.track_id?` #${o.track_id}`:""}`;const w=ctx.measureText(label).width;
 ctx.fillStyle='#10261c';ctx.fillRect(x,Math.max(0,y-15*devicePixelRatio),w+6*devicePixelRatio,15*devicePixelRatio);
 ctx.fillStyle='#caffdc';ctx.fillText(label,x+3*devicePixelRatio,Math.max(12*devicePixelRatio,y-3*devicePixelRatio));}
 state.visibleRobots=frame.robots||[];updateTrackChoices();
 const robotLabels=[];
 if($('robot-overlay').checked)for(const originalRobot of frame.robots||[]){
 const matchingTags=(state.tags||[]).filter(tag=>tag.run_id===state.autoRunId&&tag.track_id===originalRobot.track_id&&t>=tag.start&&t<=tag.end&&(tag.camera_segment==null||tag.camera_segment===originalRobot.camera_segment));
 const robot={...originalRobot};const conflictIds=new Set((state.automatic?.report?.tag_review?.conflicts||[]).flatMap(c=>c.tag_ids||[]));const teams=new Set(matchingTags.map(tag=>tag.team));if(teams.size>1||matchingTags.some(tag=>conflictIds.has(tag.id)))robot.team=null;else if(teams.size===1)robot.team=matchingTags[0].team;
 const [x1,y1,x2,y2]=robot.box,dpr=devicePixelRatio;
 const x=x1*canvas.width,y=y1*canvas.height,w=(x2-x1)*canvas.width,h=(y2-y1)*canvas.height;
 const alliance=['blue','red'].find(c=>state.match?.alliances[c]?.teams.some(t=>String(t)===String(robot.team)));
 const color=alliance==='blue'?'#66b5ff':alliance==='red'?'#ff8585':'#ffdb9e';
 ctx.setLineDash(robot.team?[]:[5*dpr,3*dpr]);
 ctx.strokeStyle='#17211c';ctx.lineWidth=5*dpr;ctx.strokeRect(x,y,w,h);
 ctx.strokeStyle=color;ctx.lineWidth=2*dpr;ctx.strokeRect(x,y,w,h);ctx.setLineDash([]);
 const label=robot.team?`Team ${robot.team}`:`Unknown · track ${robot.track_id}`;
 ctx.font=`600 ${12*dpr}px system-ui`;ctx.textBaseline='top';
 const lw=ctx.measureText(label).width+10*dpr,lh=21*dpr;
 const lx=Math.max(0,Math.min(x,canvas.width-lw));let ly=Math.max(0,y-lh);
 for(let attempt=0;attempt<30;attempt++){
  if(!robotLabels.some(r=>lx<r.x+r.w&&lx+lw>r.x&&ly<r.y+r.h&&ly+lh>r.y))break;
  ly=ly>=lh+2*dpr?ly-lh-2*dpr:Math.min(canvas.height-lh,y+h+attempt*(lh+2*dpr));
 }
 robotLabels.push({x:lx,y:ly,w:lw,h:lh});
 ctx.strokeStyle=color;ctx.lineWidth=dpr;ctx.beginPath();ctx.moveTo(x+w/2,y);ctx.lineTo(Math.max(lx,Math.min(lx+lw,x+w/2)),ly+lh);ctx.stroke();
 ctx.fillStyle='#17211c';ctx.fillRect(lx,ly,lw,lh);
 ctx.fillStyle=color;ctx.fillText(label,lx+5*dpr,ly+4*dpr);
 ctx.textBaseline='alphabetic';
 }

}
$('run-ml').onclick=guard(async()=>followJob(await api(`/api/matches/${state.match.key}/ml`,{method:'POST',body:JSON.stringify({sample_fps:Math.max(0.5,Math.round(state.match?.video_metadata?.fps || 30)),confidence:.25})})));
$('ml-overlay').onchange=drawOverlay;
$('robot-overlay').onchange=drawOverlay;
$('trajectory-overlay').onchange=drawOverlay;
$('fuel-filter').onchange=drawOverlay;
$('fuel-trajectories').onchange=drawOverlay;
$('trajectory-model').onchange=drawOverlay;
$('trajectory-rmse').oninput=drawOverlay;
$('trajectory-rejected').onchange=drawOverlay;
$('trajectory-curvature').onchange=drawOverlay;
for(const id of ['rebuild-tracks','track-gap','track-distance'])$(id).onchange=drawOverlay;
for(const id of ['hub-offset-blue','hub-offset-red','hub-padding'])$(id).oninput=drawOverlay;
$('fullscreen-overlay').onclick=()=>document.fullscreenElement?document.exitFullscreen():$('stage').requestFullscreen();
video.addEventListener('seeked',drawOverlay);
if(video.requestVideoFrameCallback){
 const redrawFrame=(_,metadata)=>{
  const data=state.autoOverlay||state.ml;
  state.overlayTime=metadata.mediaTime;
  drawOverlay();
  video.requestVideoFrameCallback(redrawFrame);
 };
 video.requestVideoFrameCallback(redrawFrame);
}else{
 const drawLoop=()=>{if(!video.paused&&!video.seeking)state.overlayTime=video.currentTime,drawOverlay();if(!video.paused)overlayRaf=requestAnimationFrame(drawLoop);};
 const startDrawLoop=()=>{if(!overlayRaf)overlayRaf=requestAnimationFrame(drawLoop);};
 const stopDrawLoop=()=>{if(overlayRaf){cancelAnimationFrame(overlayRaf);overlayRaf=0;}};
 video.addEventListener('play',startDrawLoop);
 video.addEventListener('pause',stopDrawLoop);
 video.addEventListener('ended',stopDrawLoop);
 video.addEventListener('emptied',stopDrawLoop);
}
$('ml-jump').onclick=()=>{const f=(state.autoOverlay||state.ml)?.frames.find(f=>f.objects.length);if(f){video.currentTime=f.timestamp;video.pause();drawOverlay();}};

async function loadAutomatic(key){
 if(state.autoLoadingKey===key)return;
 state.autoLoadingKey=key;
 try{
 const requestId=(state.autoRequestId||0)+1;state.autoRequestId=requestId;
 const result=await api(`/api/matches/${key}/automatic`);if(state.match?.key!==key||state.selectionKey!==key||requestId!==state.autoRequestId)return;
 const s=result.state||{},r=result.report;state.automatic=result;
 if(r){const skipped=Math.max(0,r.frames_total-r.frames_processed);$('ml-summary').textContent=`${r.frames_processed} frames received GPU detection · ${r.frames_total} source frames · ${r.frame_rate} fps source · ${r.gpu} · ${(r.elapsed_seconds/60).toFixed(1)} min processing${skipped?` · ${skipped} inactive frames skipped · analyzed ${timeLabel(r.match_window?.inference_start||0)}–${timeLabel(r.match_window?.inference_end||r.duration)}`:' · full clip analyzed'}`;$('ml-export').href=`/api/matches/${key}/automatic`;}
 $('auto-state').textContent={running:'Processing automatically',complete:'Analysis complete',failed:'Analysis needs attention',interrupted:'Waiting to resume',benchmark:'Queued for full analysis'}[s.status]||'Queued for GPU';
 const paused=s.status!=='running'&&['paused','low_disk'].includes(result.queue?.status);
 $('auto-progress-bar').value=s.progress||0;$('auto-progress-bar').hidden=s.status!=='running'||paused;$('auto-progress').hidden=s.status==='complete'&&!paused;
 $('auto-progress').classList.toggle('error',paused);
 if(paused){$('auto-state').textContent='Analysis queue paused';$('auto-progress').textContent=result.queue.reason||'More disk space is needed before automatic processing can continue. Saved results remain available.';}
 else $('auto-progress').textContent=s.error||(s.status==='running'?(s.stage==='scoreboard_scan'?`Checking the scoreboard for match timing · ${s.frames_decoded||0} source frames checked`:`Analyzing match footage · ${s.frames_processed||0} GPU frames · ${s.frames_decoded||s.frames_processed||0} / ${s.frames_total||'…'} source frames read${s.estimated_total_seconds?` · estimated ${(s.estimated_total_seconds/60).toFixed(1)} min total`:''}`):'Downloaded matches are processed automatically, one at a time.');
 if(s.status==='running'&&r&&r.run_id!==s.run_id)$('auto-progress').textContent+=' Showing previous saved estimates until this run completes.';
 const score=s.scoreboard_fuel||{};
 for(const c of ['blue','red'])$('auto-'+c).textContent=score[c]??'Pending';
 $('auto-runtime').textContent=s.elapsed_seconds?`${(s.elapsed_seconds/60).toFixed(1)} min`:'—';
 $('auto-quality').textContent=r?`Fuel-counter OCR reconciles visual crossings. Raw rim-crossing candidates: blue ${r.raw_crossing_counts.blue}, red ${r.raw_crossing_counts.red}. Robot shares are estimates, not official individual scores. TBA fuel-point reference: blue ${r.official_comparison?.blue?.tba_fuel_points??'unavailable'}, red ${r.official_comparison?.red?.tba_fuel_points??'unavailable'}. ${r.capped_frames?`${r.capped_frames} frames reached the fuel-detection cap; visual coverage is limited.`:''} Normalized robot positions appear on the video.`:'Scoreboard readings reconcile visual volleys. Uncertain robot contributions remain unassigned.';
 renderTeamScoring();
 $('auto-volleys').innerHTML=(r?.reconciliation.volleys||[]).map(v=>`<tr><td>${timeLabel(v.timestamp)}</td><td>${v.alliance}</td><td>${v.delta}</td><td>${v.detected_crossings}</td><td>${v.unassigned}</td></tr>`).join('')||'<tr><td colspan="5">Volleys appear after analysis completes.</td></tr>';
 $('auto-export').hidden=!r;$('auto-export').href=`/api/matches/${key}/automatic`;
 if(r&&state.autoRunId!==r.run_id){const hadRun=Boolean(state.autoRunId);state.tagTrack=null;state.tagEdit=null;state.tagRunId=null;$('tag-save').disabled=true;if(hadRun)$('tag-feedback').textContent='Analysis updated. Select a robot from the new playback tracks before tagging.';renderTags();const overlay=await api(`/api/matches/${key}/automatic?overlay=true`);if(state.match?.key!==key||state.selectionKey!==key||requestId!==state.autoRequestId)return;state.autoOverlay=overlay;state.autoRunId=r.run_id;drawOverlay();if(hadRun)loadTagContext(key).catch(e=>notice(e.message,true));}
 if(!r){state.autoOverlay=null;state.autoRunId=null;}
 }finally{if(state.autoLoadingKey===key)state.autoLoadingKey=null;}
}
setInterval(()=>{if(state.match)loadAutomatic(state.match.key).catch(e=>notice(e.message,true));},5000);
setInterval(()=>loadLibrary().catch(e=>notice(e.message,true)),15000);

function renderTeamScoring(){
 const r=state.automatic?.report,m=state.match;if(!m)return;
 $('prior-details').textContent=Object.values(state.priors?.teams||{}).map(p=>`${p.team}: ${p.total_epa!=null?Number(p.total_epa).toFixed(1)+' EPA points':'EPA unavailable'}${p.as_of?' · fetched '+new Date(p.as_of).toLocaleString():''}`).join('; ');
 $('auto-teams').innerHTML=['blue','red'].map(c=>m.alliances[c].teams.map(team=>{
 const estimate=r?.reconciliation?.team_estimates?.[String(team)],prior=state.priors?.teams?.[String(team)];
 const tags=state.automatic?.report?.manual_tags?.some(tag=>tag.team===team);
 const statistical=prior?.allocation??prior?.fuel_estimate,priorLabel=prior?.allocation!=null?'Alliance share approximation':prior?.fuel_estimate!=null?'Expected fuel average':null;
 return `<tr><td><span class="${c}">${team}${team===m.focus_team?' · focus':''}</span></td><td>${estimate??'Unresolved'}</td><td>${statistical!=null?escapeHtml(Number(statistical).toFixed(1)):'Unavailable'}${priorLabel?`<br><span class="source-note">${priorLabel}</span>`:''}</td><td class="source-note">${estimate!=null?(tags?'Robot tag + video':'OCR + video'):'Insufficient video evidence'}${statistical!=null?` · ${escapeHtml(prior.source||'Statbotics')}${prior.retrospective?' (retrospective)':''}`:''}</td></tr>`;
 }).join('')+`<tr><td>${c==='blue'?'Blue':'Red'} unassigned</td><td>${r?.reconciliation?.unassigned?.[c]??'Pending'}</td><td>—</td><td class="source-note">Unresolved scoreboard contribution</td></tr>`).join('');
}
async function loadTagContext(key){
 $('tag-team').innerHTML=['blue','red'].map(c=>`<optgroup label="${c} alliance">${state.match.alliances[c].teams.map(t=>`<option value="${t}">${t}</option>`).join('')}</optgroup>`).join('');
 const results=await Promise.allSettled([api(`/api/matches/${key}/tags`),api(`/api/matches/${key}/priors`)]);
 if(state.selectionKey!==key)return;
 state.tags=results[0].status==='fulfilled'?results[0].value.tags.filter(tag=>!tag.deleted):[];
 state.priors=results[1].status==='fulfilled'?results[1].value:null;
 $('tag-save').disabled=results[0].status==='rejected'||!state.tagTrack;
 $('tag-feedback').textContent=results[0].status==='rejected'?'Robot tagging is unavailable. Refresh after the service update.':'';
 renderTags();renderTeamScoring();
}
function updateTrackChoices(){
 const robots=state.visibleRobots||[],signature=robots.map(r=>r.track_id+':'+r.team).join(',');
 if(signature===state.trackChoices)return;state.trackChoices=signature;
 const value=$('tag-track').value;
 $('tag-track').innerHTML='<option value="">Choose a robot</option>'+robots.map(r=>`<option value="${r.track_id}">${r.team?'Team '+r.team:'Unknown'} · track ${r.track_id}</option>`).join('');
 if(robots.some(r=>String(r.track_id)===value))$('tag-track').value=value;
}
function visibleTrackSegment(robot,at){
 const history=state.automatic?.report?.robot_history||[];
 const samples=history.flatMap(frame=>(frame.robots||[]).filter(r=>r.track_id===robot.track_id&&(r.camera_segment??null)===(robot.camera_segment??null)).map(r=>frame.timestamp)).sort((a,b)=>a-b);
 if(!samples.length)return [Math.max(0,at-.5),Math.min(video.duration||at+.5,at+.5)];
 let nearest=0;for(let i=1;i<samples.length;i++)if(Math.abs(samples[i]-at)<Math.abs(samples[nearest]-at))nearest=i;
 let first=nearest,last=nearest;
 while(first>0&&samples[first]-samples[first-1]<=1)first--;
 while(last+1<samples.length&&samples[last+1]-samples[last]<=1)last++;
 return [samples[first],Math.max(samples[first]+.01,samples[last])];
}
function chooseRobot(robot){
 if(!robot||state.autoRunId!==state.automatic?.report?.run_id)return;video.pause();state.tagTrack=robot;state.tagEdit=null;state.tagRunId=state.autoRunId;$('tag-save').disabled=false;
 $('robot-tags').open=true;$('tag-track').value=String(robot.track_id);
 if(robot.team)$('tag-team').value=String(robot.team);
 const [segmentStart,segmentEnd]=visibleTrackSegment(robot,video.currentTime);$('tag-start').value=segmentStart.toFixed(2);$('tag-end').value=segmentEnd.toFixed(2);
 $('tag-feedback').textContent='This range covers the robot’s contiguous visible segment. Adjust it if identity changes. A tag identifies the robot; it does not create scored balls.';$('tag-cancel').hidden=true;
 $('tag-team').focus();
}
function selectRobotAt(p){
 if(!$('robot-tags').open)return;
 const candidates=(state.visibleRobots||[]).filter(r=>p[0]>=r.box[0]&&p[0]<=r.box[2]&&p[1]>=r.box[1]&&p[1]<=r.box[3]);
 candidates.sort((a,b)=>(a.box[2]-a.box[0])*(a.box[3]-a.box[1])-(b.box[2]-b.box[0])*(b.box[3]-b.box[1]));chooseRobot(candidates[0]);
}
$('robot-tags').ontoggle=()=>{$('stage').classList.toggle('tagging',$('robot-tags').open);};
$('tag-track').onchange=()=>chooseRobot((state.visibleRobots||[]).find(r=>String(r.track_id)===$('tag-track').value));
function renderTags(){
 $('tag-list').innerHTML=(state.tags||[]).map(tag=>`<p>Team ${escapeHtml(tag.team)} · ${timeLabel(tag.start)}–${timeLabel(tag.end)} ${tag.run_id===state.automatic?.report?.run_id?`<button class="quiet" data-edit-tag="${tag.id}">Edit</button><button class="quiet" data-delete-tag="${tag.id}">Undo tag</button>`:'<span class="source-note">Archived · earlier analysis</span>'}</p>`).join('');
 $('tag-list').querySelectorAll('[data-edit-tag]').forEach(b=>b.onclick=()=>{const tag=state.tags.find(t=>String(t.id)===b.dataset.editTag);if(tag.run_id!==state.automatic?.report?.run_id)return;state.tagEdit=tag;state.tagRunId=tag.run_id;$('tag-save').disabled=false;state.tagTrack={track_id:tag.track_id,box:tag.box,camera_segment:tag.camera_segment};$('tag-team').value=String(tag.team);$('tag-start').value=tag.start;$('tag-end').value=tag.end;$('tag-cancel').hidden=false;video.currentTime=tag.start;video.pause();});
 $('tag-list').querySelectorAll('[data-delete-tag]').forEach(b=>b.onclick=guard(async()=>{const key=state.match.key;b.disabled=true;try{await api(`/api/matches/${key}/tags/${b.dataset.deleteTag}`,{method:'DELETE'});await loadTagContext(key);await loadAutomatic(key);}finally{b.disabled=false;}}));
}
$('tag-cancel').onclick=()=>{state.tagEdit=null;state.tagTrack=null;$('tag-cancel').hidden=true;$('tag-feedback').textContent='Edit cancelled.';};
$('tag-save').onclick=guard(async()=>{
 if(!state.tagTrack||state.tagRunId!==state.automatic?.report?.run_id)throw new Error('Select a robot from the current analysis before saving a tag.');
 const key=state.match.key,start=Number($('tag-start').value),end=Number($('tag-end').value);
 if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start)throw new Error('End time must be later than start time.');
 const payload={run_id:state.tagRunId,track_id:state.tagTrack.track_id,camera_segment:state.tagEdit?.camera_segment??state.tagTrack.camera_segment??null,start,end,team:Number($('tag-team').value)};
 $('tag-save').disabled=true;
 try{await api(`/api/matches/${key}/tags${state.tagEdit?'/'+state.tagEdit.id:''}`,{method:state.tagEdit?'PATCH':'POST',body:JSON.stringify(payload)});state.tagEdit=null;$('tag-cancel').hidden=true;await loadTagContext(key);await loadAutomatic(key);$('tag-feedback').textContent=state.automatic?.report?.tag_review?.conflicts?.length?'Robot tag saved, but attribution has conflicting tags. Adjust overlapping tags.':`Robot tag saved. ${state.automatic?.report?.tag_review?.affected_crossings??0} crossing candidates linked to tags; unresolved scoring stays unassigned.`;}finally{$('tag-save').disabled=false;}
});
