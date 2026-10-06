"""#50 controller-facing BCB timeline (descriptive; NOT physical-person truth)."""
import glob,json,ast,sys,datetime
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
ROOT="/home/francisco/Desktop/Thesis-Code/bags/live_camera/"
RUNS=[("F1","baseline_a","2026-10-02__15-37-40","bcb_baseline_a",ROOT+"2026-10-02__15-37-40__video__bcb_baseline_a/run_logs/operator_events.jsonl"),
      ("F2","candidate","2026-10-02__15-49-03","bcb_candidate","/home/francisco/Desktop/Thesis-Code/ros2_ws/log/live_stack/2026-10-02__15-49-03/operator_events.jsonl"),
      ("F3","baseline_b","2026-10-02__15-58-43","bcb_baseline_b",ROOT+"2026-10-02__15-58-43__video__bcb_baseline_b/run_logs/operator_events.jsonl")]
def utc(s): return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
def evs(p):
    out=[]
    for l in open(p):
        d=json.loads(l); det=d.get("detail")
        if isinstance(det,str):
            try: det=ast.literal_eval(det)
            except Exception: det={"raw":det}
        out.append((utc(d["ts_utc"]),d["event"],det))
    return out
res={}
for lab,role,rid,tag,evp in RUNS:
    bag=ROOT+rid+"__video__"+tag
    f=glob.glob(bag+"/*.mcap")[0]
    if lab=="F2": f=glob.glob("/home/francisco/flight_recovery_20261002/"+rid+"__video__"+tag+"/*.mcap")[0]
    r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=f,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
    ty={t.name:t.type for t in r.get_all_topics_and_types()}
    keep=["/mavros/state","/control_ref/diagnostics","/control_ref/cmd_vel","/mavros/setpoint_velocity/cmd_vel"]
    r.set_filter(rosbag2_py.StorageFilter(topics=[k for k in keep if k in ty]))
    st=[];dg=[];cv=[];mv=[]
    while r.has_next():
        tp,d,t=r.read_next(); m=deserialize_message(d,get_message(ty[tp])); ts=m.header.stamp.sec+m.header.stamp.nanosec/1e9 if hasattr(m,"header") else t/1e9
        if tp=="/mavros/state": st.append((t/1e9,m.armed,m.mode))
        elif tp=="/control_ref/diagnostics": dg.append((ts,m.mode,m.reason,m.tim_state,m.recovery_active,m.recovery_enabled))
        elif tp=="/control_ref/cmd_vel": cv.append((ts,m.twist.linear.x,m.twist.linear.y,m.twist.linear.z,m.twist.angular.z))
        else: mv.append((ts,m.twist.linear.x,m.twist.linear.y,m.twist.linear.z,m.twist.angular.z))
    g0=next(t for t,a,mo in st if mo=="GUIDED"); g1=next(t for t,a,mo in st if t>g0 and mo!="GUIDED")
    events=evs(evp)
    opp={}
    for ts,e,det in events:
        if e in("opportunity_start","opportunity_end") and isinstance(det,dict) and "opportunity_id" in det:
            opp.setdefault(det["opportunity_id"],[]).append((e,ts,det.get("outcome")))
    # intervals of controller mode
    def seg(a,b):
        s=[(ts,mo,rs,ti,ra) for ts,mo,rs,ti,ra,_ in dg if a<=ts<=b]
        if not s: return {}
        occ={};gaps=[];cur=None;recs=[]
        for i,(ts,mo,rs,ti,ra) in enumerate(s):
            dt=(s[i+1][0]-ts) if i+1<len(s) else 0.0
            dt=min(dt,0.5)
            occ[mo]=occ.get(mo,0)+dt
        # gaps: contiguous HOVER/RECOVERY runs preceded by >=3 s of NORMAL_FOLLOW
        run_nf=0.0;start=None;prev_mo=None;prev_ts=None;nf_before=0.0;nf_acc=0.0
        for i,(ts,mo,rs,ti,ra) in enumerate(s):
            dt=(ts-s[i-1][0]) if i else 0.0
            if mo=="NORMAL_FOLLOW":
                if start is not None:
                    gaps.append(dict(start=start,end=ts,dur=round(ts-start,3),nf_before=round(nf_before,2),returned=True,recovery=any(x for x in recs)));start=None;recs=[]
                nf_acc+=dt
            else:
                if start is None: start=s[i-1][0] if i else ts; nf_before=nf_acc; nf_acc=0.0; recs=[]
                recs.append(ra)
        if start is not None: gaps.append(dict(start=start,end=s[-1][0],dur=round(s[-1][0]-start,3),nf_before=round(nf_before,2),returned=False,recovery=any(recs)))
        return dict(occupancy_s={k:round(v,2) for k,v in occ.items()},gaps=gaps,
                    recovery_active_s=round(sum(min((s[i+1][0]-s[i][0]),0.5) for i in range(len(s)-1) if s[i][4]),3),
                    recovery_activations=sum(1 for i in range(len(s)) if s[i][4] and (i==0 or not s[i-1][4])))
    def cmds(a,b,series):
        x=[v for v in series if a<=v[0]<=b]
        if not x: return {}
        nz=[i for i,v in enumerate(x) if any(abs(c)>1e-6 for c in v[1:])]
        dur=sum(min(x[i+1][0]-x[i][0],0.5) for i in nz if i+1<len(x))
        return dict(n=len(x),nonzero_s=round(dur,2),max_abs_vx=round(max(abs(v[1]) for v in x),3),max_abs_vy=round(max(abs(v[2]) for v in x),3),max_abs_vz=round(max(abs(v[3]) for v in x),3),max_abs_wz=round(max(abs(v[4]) for v in x),3),
                    wz_at_0p20=sum(1 for v in x if abs(abs(v[4])-0.20)<1e-3),recovery_translation=sum(1 for v in x if False))
    out=dict(role=role,bag=f,guided=[g0,g1],guided_s=round(g1-g0,1),
      guided_window=seg(g0,g1),guided_cmd=cmds(g0,g1,cv),guided_mavros_cmd=cmds(g0,g1,mv),
      outside_guided_cmd=cmds(0,g0-0.001,cv) , after_guided_cmd=cmds(g1,1e12,cv),
      after_guided_recovery_activations=seg(g1,1e12).get("recovery_activations"),
      opportunities={})
    for k,v in sorted(opp.items()):
        out["opportunities"][k]=dict(markers=[(e,datetime.datetime.fromtimestamp(ts,datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3],o) for e,ts,o in v])
    # opportunity windows: first start to last end of that id (F2 O2: last pair per operator correction)
    for k,v in opp.items():
        starts=[ts for e,ts,o in v if e=="opportunity_start"]; ends=[ts for e,ts,o in v if e=="opportunity_end"]
        if lab=="F2" and k=="O2": starts=[max(starts)] if starts else starts; ends=[max(ends)] if ends else ends
        if not starts or not ends:
            out["opportunities"][k]["window"]="incomplete markers"; continue
        a,b=min(starts),max(ends); w=seg(a,b)
        out["opportunities"][k].update(window_utc=[a,b],window_s=round(b-a,1),in_guided=(a>=g0 and b<=g1),overlap_guided_s=round(max(0,min(b,g1)-max(a,g0)),1),**{"ctrl":w})
    out["trial_end_utc"]=next((ts for ts,e,d in events if e=="trial_end"),None)
    res[lab]=out
json.dump(res,open("/home/francisco/flight_evidence_20261006_dataflash/bcb/bcb_timeline.json","w"),indent=1,default=str)
for lab,o in res.items():
    print("==",lab,o["role"],"guided_s",o["guided_s"],"occ",o["guided_window"].get("occupancy_s"),"recov_act",o["guided_window"].get("recovery_activations"),o["guided_window"].get("recovery_active_s"),"after_guided_recov",o["after_guided_recovery_activations"])
    print("  cmd GUIDED",o["guided_cmd"]); print("  mavros cmd GUIDED",o["guided_mavros_cmd"]); print("  after-guided cmd",o["after_guided_cmd"])
    for k,v in o["opportunities"].items():
        print("  ",k,{kk:vv for kk,vv in v.items() if kk not in("ctrl","markers")}, "gaps>=0.5s:",[ (g["dur"],g["returned"]) for g in v.get("ctrl",{}).get("gaps",[]) if g["dur"]>=0.5][:12])
