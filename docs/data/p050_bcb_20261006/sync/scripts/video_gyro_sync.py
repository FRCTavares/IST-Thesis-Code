"""Video-motion vs gyro time synchronisation (independent of tracker output). Flight 3.
Convention (as existing evaluations): source_launch_rel = video_pts + delta."""
import glob,csv,json,sys,datetime,os
import numpy as np, cv2
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
RUN=sys.argv[1]; TAG=sys.argv[2]; STARTED=sys.argv[3]; F0=int(sys.argv[4]); F1=int(sys.argv[5]); OUT=sys.argv[6]
BAG=glob.glob("/home/francisco/Desktop/Thesis-Code/bags/live_camera/%s__video__%s/*.mcap"%(RUN,TAG))
BAG=BAG[0] if RUN!="2026-10-02__15-49-03" else glob.glob("/home/francisco/flight_recovery_20261002/%s__video__%s/*.mcap"%(RUN,TAG))[0]
FR="/home/francisco/final_campaign_20261003/frames/"
DS="/home/francisco/final_campaign_20261003/mac_bundle/datasets/flights_20261002/"
fl={"bcb_baseline_a":"flight_1_baseline_a","bcb_candidate":"flight_2_candidate","bcb_baseline_b":"flight_3_baseline_b"}[TAG]
L=datetime.datetime.fromisoformat(STARTED.replace("Z","+00:00")).timestamp()
os.makedirs(OUT,exist_ok=True)
# --- gyro
r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=BAG,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
ty={t.name:t.type for t in r.get_all_topics_and_types()}; r.set_filter(rosbag2_py.StorageFilter(topics=["/mavros/imu/data_raw"]))
T=[];W=[]
while r.has_next():
    tp,d,t=r.read_next(); m=deserialize_message(d,get_message(ty[tp]))
    T.append(m.header.stamp.sec+m.header.stamp.nanosec/1e9-L); W.append((m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z))
T=np.array(T);W=np.array(W); o=np.argsort(T);T=T[o];W=W[o]
print("imu samples",len(T),"rate",len(T)/(T[-1]-T[0]),"span",T[0],T[-1],flush=True)
G=np.vstack([np.zeros(3),np.cumsum((W[1:]+W[:-1])/2*np.diff(T)[:,None],axis=0)])   # integrated angle (rad) per axis
def Gi(s): return np.stack([np.interp(s,T,G[:,k]) for k in range(3)],axis=-1)
# --- frames
rows=list(csv.DictReader(open(DS+fl+"/frame_manifest.csv")))
pts=np.array([float(x["video_pts_seconds"]) for x in rows])
idx=[i for i in range(F0,F1) if i+1<len(rows)]
prev=None; flow=[]
for i in idx:
    a=cv2.imread(FR+fl+"/images/"+rows[i]["filename"],cv2.IMREAD_GRAYSCALE); b=cv2.imread(FR+fl+"/images/"+rows[i+1]["filename"],cv2.IMREAD_GRAYSCALE)
    p0=cv2.goodFeaturesToTrack(a,500,0.01,8)
    if p0 is None: flow.append((i,np.nan,np.nan,np.nan,0)); continue
    p1,st,er=cv2.calcOpticalFlowPyrLK(a,b,p0,None,winSize=(31,31),maxLevel=3)
    ok=st.ravel()==1; q0=p0[ok].reshape(-1,2); q1=p1[ok].reshape(-1,2)
    if len(q0)<20: flow.append((i,np.nan,np.nan,np.nan,len(q0))); continue
    M,inl=cv2.estimateAffinePartial2D(q0,q1,method=cv2.RANSAC,ransacReprojThreshold=2.0)
    if M is None: flow.append((i,np.nan,np.nan,np.nan,len(q0))); continue
    ang=np.arctan2(M[1,0],M[0,0]); flow.append((i,M[0,2],M[1,2],ang,int(inl.sum())))
flow=np.array(flow); print("flow pairs",len(flow),"valid",int(np.isfinite(flow[:,1]).sum()),flush=True)
np.savez(OUT+"/flow.npz",flow=flow,pts=pts,T=T,W=W)
# --- correlation vs delta: image shift between frames i,i+1  vs integrated gyro between s_i and s_{i+1}, s=pts+delta
i0=flow[:,0].astype(int); ok=np.isfinite(flow[:,1])
s0=pts[i0]; s1=pts[i0+1]
res=[]
deltas=np.arange(-2.0,4.0001,0.02)
for d in deltas:
    dG=Gi(s1+d)-Gi(s0+d)
    best=[]
    for name,x in (("dx",flow[:,1]),("dy",flow[:,2]),("rot",flow[:,3])):
        for k,gn in enumerate("xyz"):
            m=ok&np.isfinite(dG[:,k])
            if m.sum()<50: continue
            c=np.corrcoef(x[m],dG[m,k])[0,1]; best.append((abs(c),c,name,gn))
    res.append((float(d),max(best)))
res_arr=[(d,b[0],b[1],b[2],b[3]) for d,b in res]
top=sorted(res_arr,key=lambda x:-x[1])[:5]
print("top deltas",top)
# which pairing dominates
from collections import Counter
print("dominant pairing",Counter((x[3],x[4]) for x in res_arr).most_common(3))
json.dump(dict(top=top,profile=res_arr,frames=[F0,F1],bag=BAG,started=STARTED),open(OUT+"/sync_result.json","w"))
