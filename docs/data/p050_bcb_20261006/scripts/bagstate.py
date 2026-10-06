import sys,glob,datetime
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
for bag in sys.argv[1:]:
    f=glob.glob(bag+"/*.mcap")[0]
    r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=f,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
    types={t.name:t.type for t in r.get_all_topics_and_types()}
    keep={"/mavros/state","/mavros/battery"}
    r.set_filter(rosbag2_py.StorageFilter(topics=[k for k in keep if k in types]))
    prev=None; bat=[]; out=[]
    while r.has_next():
        tp,d,t=r.read_next(); m=deserialize_message(d,get_message(types[tp]))
        u=datetime.datetime.fromtimestamp(t/1e9,datetime.timezone.utc).strftime("%H:%M:%S")
        if tp=="/mavros/state":
            s=(m.connected,m.armed,m.mode)
            if s!=prev: out.append((u,s)); prev=s
        else: bat.append((u,round(m.voltage,2)))
    print("==",bag.split("/")[-1]); [print(" ",o) for o in out]
    if bat: print("  batt first",bat[0],"min",min(bat,key=lambda b:b[1]),"last",bat[-1])
