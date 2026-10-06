import glob,json,datetime,collections
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
R="/home/francisco/Desktop/Thesis-Code/bags/live_camera/"
runs={"F1":R+"2026-10-02__15-37-40__video__bcb_baseline_a","F2":"/home/francisco/flight_recovery_20261002/2026-10-02__15-49-03__video__bcb_candidate","F3":R+"2026-10-02__15-58-43__video__bcb_baseline_b"}
tl=json.load(open("/home/francisco/flight_evidence_20261006_dataflash/bcb/bcb_timeline.json"))
out={}
for lab,p in runs.items():
    f=glob.glob(p+"/*.mcap")[0]
    r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=f,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
    ty={t.name:t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=["/control_ref/diagnostics","/control_ref/cmd_vel"]))
    dg={};cv={};recs=[]
    while r.has_next():
        tp,d,t=r.read_next(); m=deserialize_message(d,get_message(ty[tp])); k=(m.header.stamp.sec,m.header.stamp.nanosec)
        if tp.endswith("diagnostics"): dg[k]=(m.mode,m.reason,m.status_fresh,m.target_fresh,m.target_valid,m.recovery_active)
        else: cv[k]=(m.twist.linear.x,m.twist.linear.y,m.twist.linear.z,m.twist.angular.z)
    g0,g1=tl[lab]["guided"]; ks=sorted(k for k in cv if g0<=k[0]+k[1]/1e9<=g1)
    unp=0; flagged=[]; byc=collections.OrderedDict(); dur=collections.defaultdict(float); recl=[]
    for i,k in enumerate(ks):
        dt=min((ks[i+1][0]+ks[i+1][1]/1e9-k[0]-k[1]/1e9) if i+1<len(ks) else 0,0.5)
        c=cv[k]; nz=any(abs(x)>1e-6 for x in c)
        if k not in dg: unp+=1; continue
        mode,reason,sf,tf,tv,ra=dg[k]
        rs=reason if mode!='NORMAL_FOLLOW' else 'trusted'
        key=(mode+'|'+rs+'|nonzero') if nz else (mode+'|zero')
        dur[key]+=dt
        if mode=="NORMAL_FOLLOW" and not (sf and tf and tv): dur["NORMAL_FOLLOW_with_stale_or_invalid_flag"]+=dt; dur["NF_flagged_NONZERO_cmd"]+=dt if nz else 0; flagged.append((round(k[0]+k[1]/1e9,3),c,(sf,tf,tv),reason))
        if ra: recl.append((round(k[0]+k[1]/1e9,3),c))
    # recovery samples summary
    out[lab]=dict(unpaired_cmd_samples=unp,duration_s_by_mode_reason={a:round(b,2) for a,b in dur.items()},
       recovery_samples=len(recl),recovery_t=(recl[0][0],recl[-1][0]) if recl else None,
       recovery_max_abs_linear=max((max(abs(c[0]),abs(c[1]),abs(c[2])) for _,c in recl),default=0),
       recovery_wz_values=sorted(set(round(c[3],3) for _,c in recl)),
       recovery_segments=[],flagged_samples=flagged[:20])
    # segments
    seg=[];cur=None
    for t,c in recl:
        if cur and t-cur[1]<0.1: cur[1]=t
        else:
            cur=[t,t]; seg.append(cur)
    out[lab]["recovery_segments"]=[(round(a,2),round(b,2),round(b-a+0.033,2)) for a,b in seg]
print(json.dumps(out,indent=1))
json.dump(out,open("/home/francisco/flight_evidence_20261006_dataflash/bcb/cmd_attribution2.json","w"),indent=1)
