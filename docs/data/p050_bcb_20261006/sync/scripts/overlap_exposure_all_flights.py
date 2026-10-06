import glob,csv,json,datetime,os,sys
import numpy as np, xml.etree.ElementTree as ET
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
H=os.path.expanduser("~")
FL,RUN,TAG,STARTED,G0,G1=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5]),int(sys.argv[6]); DELTAS=[float(x) for x in sys.argv[7].split(",")]
L=datetime.datetime.fromisoformat(STARTED.replace("Z","+00:00")).timestamp()
BAG=(glob.glob("/home/francisco/flight_recovery_20261002/%s__video__%s/*.mcap"%(RUN,TAG)) if TAG=="bcb_candidate" else glob.glob(H+"/Desktop/Thesis-Code/bags/live_camera/%s__video__%s/*.mcap"%(RUN,TAG)))[0]
DS=H+"/final_campaign_20261003/mac_bundle/datasets/flights_20261002/"+FL+"/"
pts={int(r["cvat_frame"]):float(r["video_pts_seconds"]) for r in csv.DictReader(open(DS+"frame_manifest.csv"))}
root=ET.parse(H+"/final_campaign_20261003/frames/"+FL+"/annotations.xml").getroot(); ann={}
for im in root.iter("image"):
    f=int(im.attrib["id"]); bs=[]
    for b in im.iter("box"):
        ref=[a.text for a in b if a.attrib.get("name")=="physical_ref"][0]; bs.append((ref,float(b.attrib["xtl"]),float(b.attrib["ytl"]),float(b.attrib["xbr"]),float(b.attrib["ybr"])))
    ann[f]=bs
def iou(a,b):
    ix=max(0,min(a[2],b[2])-max(a[0],b[0])); iy=max(0,min(a[3],b[3])-max(a[1],b[1])); i=ix*iy
    u=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i; return i/u if u>0 else 0
r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=BAG,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
ty={t.name:t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=["/target_memory_mars","/control_ref/cmd_vel"]))
A=[];CMD=[]
while r.has_next():
    tp,d,t=r.read_next(); m=deserialize_message(d,get_message(ty[tp]))
    if tp=="/target_memory_mars": A.append((m.src_stamp_ns/1e9-L,m.id,m.cx,m.cy,m.w,m.h))
    else: CMD.append((m.header.stamp.sec+m.header.stamp.nanosec/1e9-L,m.twist.linear.x,m.twist.angular.z))
A.sort();CMD.sort(); ts=np.array([a[0] for a in A]); C=np.array(CMD); ct=C[:,0]; nz=(np.abs(C[:,1])>1e-6)|(np.abs(C[:,2])>1e-6); dt=np.minimum(np.diff(ct,append=ct[-1]),0.5)
frames=[f for f in range(G0,G1+1) if any(b[0]=="target" for b in ann.get(f,[]))]
print(FL,"target-visible frames in selected GUIDED window:",len(frames))
for delta in DELTAS:
    cls={}
    for f in frames:
        s=pts[f]+delta; j=int(np.argmin(np.abs(ts-s)))
        if abs(ts[j]-s)>0.5: cls[f]="no_output"; continue
        _,i,cx,cy,w,h=A[j]
        if i<=0 or w<=0: cls[f]="no_output"; continue
        box=(cx-w/2,cy-h/2,cx+w/2,cy+h/2); sc={}
        for ref,x0,y0,x1,y1 in ann[f]: sc[ref]=max(sc.get(ref,0),iou(box,(x0,y0,x1,y1)))
        t=sc.get("target",0); comp=max([v for k,v in sc.items() if k!="target"],default=0)
        cls[f]="target_overlap" if (t>=0.30 and t>comp) else "distractor_overlap" if (comp>=0.30 and comp>t) else "unresolved_geometry"
    cnt={}
    for v in cls.values(): cnt[v]=cnt.get(v,0)+1
    fr=sorted(f for f,v in cls.items() if v=="distractor_overlap"); runs=[];cur=[]
    for f in fr:
        if cur and f==cur[-1]+1: cur.append(f)
        else:
            if cur: runs.append(cur)
            cur=[f]
    if cur: runs.append(cur)
    tot=0;nzt=0
    for run in runs:
        a=pts[run[0]]-(pts[run[0]]-pts[run[0]-1])/2+delta; b=pts[run[-1]]+(pts[run[-1]+1]-pts[run[-1]])/2+delta; tot+=b-a
        m=(ct>=a)&(ct<b); nzt+=float((dt[m]*nz[m]).sum())
    print("delta %.2f"%delta,cnt,"distractor intervals %.2fs, non-zero cmd in them %.2fs"%(tot,nzt),flush=True)
