import glob,json
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
B=glob.glob("/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/*.mcap")[0]
START=1791294856.402980787+(340623757271181-340623596717100)/1e9; END=START+1260.0; WARM=START+60
r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=B,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
ty={t.name:t.type for t in r.get_all_topics_and_types()}
F={"/timing":"e2e_det_ms","/timing_tracker":"track_ms","/timing_target":"e2e_validated_target_ms","/control_ref/cmd_vel":None,"/target_memory_mars":None}
r.set_filter(rosbag2_py.StorageFilter(topics=list(F)))
D={k:[] for k in F}
while r.has_next():
    tp,d,t=r.read_next(); ts=t/1e9
    if ts<START or ts>END: continue
    m=deserialize_message(d,get_message(ty[tp])); f=F[tp]
    D[tp].append((ts,getattr(m,f) if f else 0.0))
def stats(a,lo):
    a=[x for x in a if x[0]>=lo]; t=np.array([x[0] for x in a]); v=np.array([x[1] for x in a]); g=np.diff(t)*1000
    o={"n":len(a),"rate_hz":round(len(a)/(max(t)-min(t)),3) if len(a)>1 else 0,"gap_ms_p50":round(float(np.percentile(g,50)),1),"gap_ms_p95":round(float(np.percentile(g,95)),1),"gap_ms_p99":round(float(np.percentile(g,99)),1),"gap_ms_max":round(float(g.max()),1)}
    if v.any(): o.update({"lat_ms_p50":round(float(np.percentile(v,50)),1),"lat_ms_p95":round(float(np.percentile(v,95)),1),"lat_ms_p99":round(float(np.percentile(v,99)),1),"lat_ms_max":round(float(v.max()),1)})
    return o
out={}
for tp in F:
    out[tp]={"full_bounded_1260s":stats(D[tp],START),"post_warmup_1200s":stats(D[tp],WARM)}
    print(tp); print("  full:",out[tp]["full_bounded_1260s"]); print("  post:",out[tp]["post_warmup_1200s"])
json.dump(out,open("/home/francisco/flight_evidence_20261006_dataflash/p032_bounded_window_stats.json","w"),indent=1)
