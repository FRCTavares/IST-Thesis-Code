import json,numpy as np,os
H=os.path.expanduser("~"); D=H+"/flight_evidence_20261006_dataflash/f3_sync/"
ov=json.load(open(D+"overlap_by_offset.json")); C=np.load(D+"cmd_launchrel.npy")   # t, vx, wz
ct=C[:,0]; nz=(np.abs(C[:,1])>1e-6)|(np.abs(C[:,2])>1e-6)
dt=np.minimum(np.diff(ct,append=ct[-1]),0.5)
def runs(frames):
    out=[];cur=[]
    for f in frames:
        if cur and f==cur[-1]+1: cur.append(f)
        else:
            if cur: out.append(cur)
            cur=[f]
    if cur: out.append(cur)
    return out
import csv
pts={int(r["cvat_frame"]):float(r["video_pts_seconds"]) for r in csv.DictReader(open(H+"/final_campaign_20261003/mac_bundle/datasets/flights_20261002/flight_3_baseline_b/frame_manifest.csv"))}
print("delta  distractor_frames  runs  interval_s  nonzero_cmd_in_intervals_s  frames_with_nonzero_cmd")
res={}
for key in sorted(ov):
    delta=float(key.split("|")[1])
    fr=sorted(int(f) for f,v in ov[key].items() if v[0]=="distractor_overlap")
    R=runs(fr); tot=0;nzt=0;nzf=0; ints=[]
    for run in R:
        a=pts[run[0]]-(pts[run[0]]-pts[run[0]-1])/2+delta; b=pts[run[-1]]+(pts[run[-1]+1]-pts[run[-1]])/2+delta
        ints.append((round(a,2),round(b,2))); tot+=b-a
        m=(ct>=a)&(ct<b); nzt+=float((dt[m]*nz[m]).sum())
    for f in fr:
        s=pts[f]+delta; j=int(np.argmin(np.abs(ct-s))); nzf+=int(nz[j] and abs(ct[j]-s)<0.3)
    res[key]=(len(fr),len(R),round(tot,2),round(nzt,2),nzf,ints)
    print("%5.2f  %3d  %2d  %6.2f  %6.2f  %3d"%(delta,len(fr),len(R),tot,nzt,nzf))
for k in ("/target_memory_mars|1.02",):
    print(k,"intervals (launch-rel s):",res[k][5])
json.dump(res,open(D+"f3_wrong_person_exposure.json","w"),indent=1)
