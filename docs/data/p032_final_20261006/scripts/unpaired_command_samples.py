import glob,json,datetime
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
B=glob.glob("/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/*.mcap")[0]
r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=B,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
ty={t.name:t.type for t in r.get_all_topics_and_types()}
T=["/control_ref/cmd_vel","/control_ref/diagnostics","/mavros/setpoint_velocity/cmd_vel"]
r.set_filter(rosbag2_py.StorageFilter(topics=T))
S={t:{} for t in T}; first=last=None
while r.has_next():
    tp,d,t=r.read_next(); m=deserialize_message(d,get_message(ty[tp])); k=m.header.stamp.sec*10**9+m.header.stamp.nanosec
    S[tp].setdefault(k,[]).append((t,tuple(round(x,4) for x in (m.twist.linear.x,m.twist.linear.y,m.twist.linear.z,m.twist.angular.z)) if hasattr(m,"twist") else None))
    first=t if first is None else first; last=t
c=set(S[T[0]]); dg=set(S[T[1]]); mv=set(S[T[2]])
print("cmd",len(c),"diag",len(dg),"mavros",len(mv))
U=lambda ns:datetime.datetime.fromtimestamp(ns/1e9,datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
print("bag span UTC",U(first),U(last))
for name,x in (("cmd not in diag",c-dg),("cmd not in mavros",c-mv),("diag not in cmd",dg-c),("mavros not in cmd",mv-c)):
    print(name,len(x),[(U(k),S[T[0]].get(k,[None])[0][1] if k in S[T[0]] else None) for k in sorted(x)][:6])
dups=[k for k,v in S[T[0]].items() if len(v)>1]; print("duplicate cmd stamps",len(dups))
