"""Image-scale-aware curved-flight evidence, including partial arcs."""
import numpy as np


def observed_arc(points):
    if len(points)<9:return False
    data=np.asarray(points,dtype=float);t=data[:,0]-data[0,0];duration=t[-1]
    if not .12<=duration<=3 or np.max(np.diff(t))>.15:return False
    sizes=np.maximum(data[:,3:5],1e-5) if data.shape[1]>=5 else np.full((len(t),2),.006)
    scale=np.median(sizes,axis=0)
    xy=(data[:,1:3]-data[0,1:3])/scale
    design=np.column_stack((np.ones(len(t)),t,t*t))
    fit=np.linalg.lstsq(design,xy,rcond=None)[0]
    residual=np.sqrt(np.mean(np.sum(((design@fit-xy)*scale/sizes)**2,axis=1)))
    line=design[:,:2]@np.linalg.lstsq(design[:,:2],xy,rcond=None)[0]
    linear_error=np.sqrt(np.mean(np.sum(((line-xy)*scale/sizes)**2,axis=1)))
    # Compare curvature and residual to apparent ball diameters, not fixed pixels.
    bend=np.linalg.norm(fit[2])*duration*duration/4
    travel=np.linalg.norm(np.ptp(xy,axis=0))
    if fit[2,1]>0 and bend>=.35 and travel>=2 and residual<=.6 and linear_error>max(.12,residual*1.35):
        return True
    # A cubic is a fallback for smooth perspective-distorted flight, not a
    # license to fit a few noisy detections. Normalize time for conditioning.
    if len(t)<16 or duration<.2 or travel<2:return False
    u=t/duration
    cubic_design=np.column_stack((np.ones(len(u)),u,u*u,u*u*u))
    cubic=np.linalg.lstsq(cubic_design,xy,rcond=None)[0]
    predicted=cubic_design@cubic
    cubic_error=np.sqrt(np.mean(np.sum(((predicted-xy)*scale/sizes)**2,axis=1)))
    chord=predicted[0]+u[:,None]*(predicted[-1]-predicted[0])
    cubic_bend=np.max(np.linalg.norm(predicted-chord,axis=1))
    # Vertical acceleration of a cubic is linear: endpoint checks ensure
    # downward curvature throughout the observed path, rejecting S-shaped jitter.
    acceleration=2*cubic[2,1]+6*cubic[3,1]*np.array([0.,1.])
    return bool(np.min(acceleration)>0 and cubic_bend>=.35 and cubic_error<=.6
                and cubic_error<residual*.75
                and linear_error>max(.12,cubic_error*1.35))
