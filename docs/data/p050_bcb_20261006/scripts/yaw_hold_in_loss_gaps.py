"""FCU yaw rate (DataFlash RATE.Y, deg/s) during the zero-command controller loss gaps versus 30 s following windows.
Bag->log alignment: GUIDED start in the bag (UTC) matches GUIDED start in the log (s); about +-0.5 s uncertainty."""
from pymavlink import mavutil
import datetime
def U(h):
    t=datetime.datetime.strptime(h,"%H:%M:%S.%f"); return t.hour*3600+t.minute*60+t.second+t.microsecond/1e6
cases=[("F1","log_23.bin",807.0,U("14:40:44.98"),("loss gap","14:42:20.39","14:42:36.33"),("follow","14:43:20.0","14:43:50.0")),
       ("F2","log_24.bin",1515.1,U("14:52:33.18"),("loss gap","14:54:10.63","14:54:25.24"),("follow","14:53:00.0","14:53:30.0")),
       ("F3","log_26.bin",266.6,U("15:02:13.36"),("loss gap","15:03:06.98","15:03:19.16"),("follow","15:03:40.0","15:04:10.0"))]
for lab,f,g0,b0,*wins in cases:
    m=mavutil.mavlink_connection(f); R=[]
    while True:
        x=m.recv_match(type="RATE",blocking=False)
        if x is None: break
        R.append((x.TimeUS/1e6,x.YDes,x.Y))
    for name,a,b in wins:
        lo=g0+(U(a)-b0); hi=g0+(U(b)-b0); v=[(yd,y) for t,yd,y in R if lo<=t<=hi]
        print(lab,name,"n=%d mean|YDes|=%.2f mean|Y|=%.2f max|Y|=%.2f deg/s"%(len(v),sum(abs(a) for a,_ in v)/len(v),sum(abs(y) for _,y in v)/len(v),max(abs(y) for _,y in v)))
