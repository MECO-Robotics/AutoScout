/* Pure polynomial regression shared by browser playback and regression tests. */
(function(root){
function fit(points,degree,maxGap=.15){
 if(points.length<degree+2)return null;
 const start=points[0][0],duration=points.at(-1)[0]-start;
 if(duration<=0||points.some((p,i)=>i&&p[0]-points[i-1][0]>maxGap))return null;
 const n=degree+1,A=Array.from({length:n},()=>Array(n+2).fill(0));
 for(const p of points){const u=(p[0]-start)/duration,powers=Array.from({length:2*n},(_,i)=>u**i);for(let i=0;i<n;i++){for(let j=0;j<n;j++)A[i][j]+=powers[i+j];A[i][n]+=powers[i]*p[1];A[i][n+1]+=powers[i]*p[2];}}
 for(let i=0;i<n;i++){let pivot=i;for(let j=i+1;j<n;j++)if(Math.abs(A[j][i])>Math.abs(A[pivot][i]))pivot=j;[A[i],A[pivot]]=[A[pivot],A[i]];const v=A[i][i];if(Math.abs(v)<1e-10)return null;for(let j=i;j<n+2;j++)A[i][j]/=v;for(let k=0;k<n;k++)if(k!==i){const r=A[k][i];for(let j=i;j<n+2;j++)A[k][j]-=r*A[i][j];}}
 const coefficients=A.map(r=>r.slice(n));
 const evaluate=u=>coefficients.reduce((v,c,i)=>[v[0]+c[0]*u**i,v[1]+c[1]*u**i],[0,0]);
 const rmse=Math.sqrt(points.reduce((sum,p)=>{const q=evaluate((p[0]-start)/duration);return sum+((q[0]-p[1])/Math.max(p[3],1e-5))**2+((q[1]-p[2])/Math.max(p[4],1e-5))**2;},0)/points.length);
 const path=Array.from({length:49},(_,i)=>[start+duration*i/48,...evaluate(i/48)]);
 const diameter=points.reduce((s,p)=>s+Math.max(p[3],p[4]),0)/points.length;
 const first=path[0],last=path.at(-1);
 const bend=Math.max(...path.map((p,i)=>Math.hypot(p[1]-(first[1]+(last[1]-first[1])*i/48),p[2]-(first[2]+(last[2]-first[2])*i/48))))/Math.max(diameter,1e-5);
 return {degree,rmse,points:path,start,end:start+duration,coefficients,curved:bend>=.35};
}
function track(frames,{gap=.15,distance=3}={}){
 const tracks=new Map(),lookup=new Map();let active=new Map(),next=1,segment=null;
 for(const frame of frames){
  const t=frame.timestamp;
  if(segment!==frame.camera_segment){active.clear();segment=frame.camera_segment;}
  for(const [id,r] of active)if(t-r.time>gap)active.delete(id);
  const objects=frame.objects||[],pairs=[];
  const centers=objects.map(o=>[(o.box[0]+o.box[2])/2,(o.box[1]+o.box[3])/2]);
  for(const [id,r] of active)for(let j=0;j<objects.length;j++){
   const box=objects[j].box,dt=t-r.time;
   const dx=(centers[j][0]-r.x-r.vx*dt)/Math.max(.001,box[2]-box[0],r.w);
   const dy=(centers[j][1]-r.y-r.vy*dt)/Math.max(.001,box[3]-box[1],r.h);
   const cost=Math.hypot(dx,dy);if(cost<=distance)pairs.push([cost,id,j]);
  }
  pairs.sort((a,b)=>a[0]-b[0]);const used=new Set(),assigned=new Map();
  for(const [cost,id,j] of pairs)if(!used.has(id)&&!assigned.has(j)){used.add(id);assigned.set(j,id);}
  objects.forEach((o,j)=>{const id=assigned.get(j)??next++,old=active.get(id),[x,y]=centers[j],box=o.box,dt=old?t-old.time:0;
   const r={x,y,w:box[2]-box[0],h:box[3]-box[1],time:t,vx:dt>0?(x-old.x)/dt:0,vy:dt>0?(y-old.y)/dt:0};active.set(id,r);
   if(!tracks.has(id))tracks.set(id,[]);tracks.get(id).push([t,x,y,r.w,r.h]);lookup.set(`${t}:${j}`,id);
  });
 }
 return {tracks,lookup};
}
root.TrajectoryFit={fit,track};if(typeof module!=='undefined')module.exports=root.TrajectoryFit;
})(typeof globalThis!=='undefined'?globalThis:this);
