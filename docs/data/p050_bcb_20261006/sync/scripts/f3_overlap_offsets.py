import glob,csv,json,datetime,os,sys
import numpy as np, xml.etree.ElementTree as ET
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
H=os.path.expanduser("~")
L=datetime.datetime.fromisoformat("2026-10-02T14:59:46.825260970+00:00").timestamp()
BAG=glob.glob(H+"/Desktop/Thesis-Code/bags/live_camera/2026-10-02__15-58-43__video__bcb_baseline_b/*.mcap")[0]
DS=H+"/final_campaign_20261003/mac_bundle/datasets/flights_20261002/flight_3_baseline_b/"
pts={int(r["cvat_frame"]):float(r["video_pts_seconds"]) for r in csv.DictReader(open(DS+"frame_manifest.csv"))}
root=ET.parse(H+"/final_campaign_20261003/frames/flight_3_baseline_b/annotations.xml").getroot()
ann={}
for im in root.iter("image"):
    f=int(im.attrib["id"]); bs=[]
    for b in im.iter("box"):
        ref=[a.text for a in b if a.attrib.get("name")=="physical_ref"][0]
        bs.append((ref,float(b.attrib["xtl"]),float(b.attrib["ytl"]),float(b.attrib["xbr"]),float(b.attrib["ybr"])))
    ann[f]=bs
def iou(a,b):
    ix=max(0,min(a[2],b[2])-max(a[0],b[0])); iy=max(0,min(a[3],b[3])-max(a[1],b[1])); i=ix*iy
    u=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i; return i/u if u>0 else 0
r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=BAG,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
ty={t.name:t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=["/target_memory_mars","/target","/control_ref/cmd_vel","/control_ref/diagnostics"]))
M={"/target_memory_mars":[],"/target":[]}; CMD=[]
while r.has_next():
    tp,d,t=r.read_next(); m=deserialize_message(d,get_message(ty[tp]))
    if tp in M:
        s=m.src_stamp_ns/1e9-L; M[tp].append((s,m.id,m.cx,m.cy,m.w,m.h))
    elif tp=="/control_ref/cmd_vel":
        CMD.append((m.header.stamp.sec+m.header.stamp.nanosec/1e9-L,m.twist.linear.x,m.twist.angular.z))
for k in M: M[k].sort()
CMD.sort()
GUIDED=(916,1469)
frames=[f for f in range(GUIDED[0],GUIDED[1]+1) if any(b[0]=="target" for b in ann.get(f,[]))]
print("target-visible frames in selected GUIDED window:",len(frames))
def classify(topic,delta):
    arr=M[topic]; ts=np.array([a[0] for a in arr]); out={}
    for f in frames:
        s=pts[f]+delta; j=int(np.argmin(np.abs(ts-s)))
        if abs(ts[j]-s)>0.5: out[f]=("no_output",None,None,s); continue
        _,i,cx,cy,w,h=arr[j]
        if i<=0 or w<=0: out[f]=("no_output",None,None,s); continue
        box=(cx-w/2,cy-h/2,cx+w/2,cy+h/2)
        sc={}
        for ref,x0,y0,x1,y1 in ann[f]: sc[ref]=max(sc.get(ref,0),iou(box,(x0,y0,x1,y1)))
        t=sc.get("target",0); comp=max([v for k,v in sc.items() if k!="target"],default=0)
        if t>=0.30 and t>comp: c="target_overlap"
        elif comp>=0.30 and comp>t: c="distractor_overlap"
        elif max(t,comp)>=0.30: c="unresolved_geometry"
        else: c="unresolved_geometry" if max(t,comp)>0 else "unresolved_geometry"
        out[f]=(c,i,(round(t,3),round(comp,3)),s)
    return out
res={}
for topic in ("/target_memory_mars","/target"):
    for d in (0.62,0.87,0.94,1.02,1.10,1.12,1.37,1.62):
        o=classify(topic,d); cnt={}
        for v in o.values(): cnt[v[0]]=cnt.get(v[0],0)+1
        res[(topic,d)]=o; print(topic,d,cnt,flush=True)
# per-frame detail for TIM at 1.02 / 1.12
json.dump({"%s|%.2f"%k:{str(f):v for f,v in o.items()} for k,o in res.items() if k[0]=="/target_memory_mars"},open(H+"/flight_evidence_20261006_dataflash/f3_sync/overlap_by_offset.json","w"),default=str)
np.save(H+"/flight_evidence_20261006_dataflash/f3_sync/cmd_launchrel.npy",np.array(CMD))
