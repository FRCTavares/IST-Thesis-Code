import sys
from pymavlink import mavutil
for f in sys.argv[1:]:
    m=mavutil.mavlink_connection(f)
    modes=[];ev=[];bat=[];err=[];msgs=[];alt=[];t0=t1=None
    while True:
        x=m.recv_match(blocking=False)
        if x is None: break
        ty=x.get_type(); t=getattr(x,"TimeUS",None)
        if t is None: continue
        t/=1e6; t0=t if t0 is None else t0; t1=t
        if ty=="MODE": modes.append((round(t,1),x.Mode,getattr(x,"ModeNum",None)))
        elif ty=="EV" and x.Id in (10,11,15,16,17,18): ev.append((round(t,1),{10:"ARM",11:"DISARM",15:"AUTO_ARMED",17:"LAND_COMPLETE_MAYBE",18:"LAND_COMPLETE"}.get(x.Id,x.Id)))
        elif ty=="BAT": bat.append((t,x.Volt,getattr(x,"CurrTot",None)))
        elif ty=="ERR": err.append((round(t,1),x.Subsys,x.ECode))
        elif ty=="MSG": msgs.append((round(t,1),x.Message))
        elif ty=="BARO" or ty=="CTUN": 
            a=getattr(x,"Alt",None) or getattr(x,"BAlt",None)
            if a is not None: alt.append((t,a))
    print("==",f,"span",round(t1-t0,1))
    print("modes",modes); print("events",ev); print("errors",err)
    if bat: print("batt first/min/last V", round(bat[0][1],2), round(min(b[1] for b in bat),2), round(bat[-1][1],2), "at_min_t",round(min(bat,key=lambda b:b[1])[0],1))
    if alt: print("max alt",round(max(a for _,a in alt),1))
    print("msgs",[m for m in msgs if any(k in m[1].lower() for k in("batt","fail","land","arm","rtl","gps","ekf","crash","thrust"))][:25])
