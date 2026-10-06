import numpy as np, json
Z=np.load("/home/francisco/flight_evidence_20261006_dataflash/f3_sync/flow.npz")
flow,pts,T,W=Z["flow"],Z["pts"],Z["T"],Z["W"]
G=np.concatenate([[0],np.cumsum((W[1:,2]+W[:-1,2])/2*np.diff(T))])
Gi=lambda s:np.interp(s,T,G)
i0=flow[:,0].astype(int); s0=pts[i0]; s1=pts[i0+1]; dx=flow[:,1]
def corr(idx,d):
    dG=Gi(s1[idx]+d)-Gi(s0[idx]+d); return np.corrcoef(dx[idx],dG)[0,1]
ds=np.arange(-1,3.0001,0.01)
allidx=np.arange(len(dx))
prof=np.array([corr(allidx,d) for d in ds])
b=ds[np.argmax(np.abs(prof))]; print("global best delta",round(b,2),"corr",round(prof[np.argmax(np.abs(prof))],4))
for d in (0.52,0.87,1.02,1.12,1.37,1.62): print(" corr at delta",d,round(corr(allidx,d),4))
half=[d for d,c in zip(ds,np.abs(prof)) if c>=0.99*np.abs(prof).max()]; print("delta range with corr>=99% of peak:",round(min(half),2),round(max(half),2))
# scale (px per rad) at best delta
dG=Gi(s1+b)-Gi(s0+b); k=np.polyfit(dG,dx,1); print("slope px/rad",round(k[0],1),"(f~ px)","resid rms px",round(np.std(dx-np.polyval(k,dG)),2),"dx rms",round(np.std(dx),2))
# pair time spacing
print("pair dt: median",round(float(np.median(s1-s0)),3),"p90",round(float(np.percentile(s1-s0,90)),3),"max",round(float((s1-s0).max()),2))
# windows
print("windows (pts range, best delta, corr):")
n=len(dx); step=120
for a in range(0,n-step+1,step):
    ix=np.arange(a,a+step); pr=np.array([corr(ix,d) for d in ds]); j=np.argmax(np.abs(pr))
    print("  pts %6.1f-%6.1f  delta %.2f corr %.3f"%(s0[ix[0]],s1[ix[-1]],ds[j],pr[j]))
# bootstrap CI
rng=np.random.default_rng(0); bs=[]
for _ in range(200):
    ix=np.sort(rng.choice(allidx,len(allidx),replace=True)); pr=np.array([corr(ix,d) for d in np.arange(0.5,1.6,0.02)]); bs.append(np.arange(0.5,1.6,0.02)[np.argmax(np.abs(pr))])
print("bootstrap delta 2.5/50/97.5 pct:",np.percentile(bs,[2.5,50,97.5]).round(2))
