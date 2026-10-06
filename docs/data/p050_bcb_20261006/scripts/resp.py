import sys, json, statistics as st
from pymavlink import mavutil
def load(f):
    m=mavutil.mavlink_connection(f); d={k:[] for k in("MODE","EV","ATT","RATE","CTUN","RCIN","BAT","POS","XKF1")}
    while True:
        x=m.recv_match(type=list(d),blocking=False)
        if x is None: break
        d[x.get_type()].append(x)
    return d
def T(x): return x.TimeUS/1e6
out={}
for f,lab in [("log_23.bin","F1"),("log_24.bin","F2"),("log_26.bin","F3")]:
    d=load(f)
    modes=[(T(x),x.ModeNum) for x in d["MODE"]]
    g0=[t for t,mn in modes if mn==4][0]
    g1=[t for t,mn in modes if t>g0 and mn!=4][0]
    arm=[T(x) for x in d["EV"] if x.Id==10 or x.Id==15][0]; dis=[T(x) for x in d["EV"] if x.Id==11][0]
    land=[T(x) for x in d["EV"] if x.Id==18][0]
    def win(k,a,b): return [x for x in d[k] if a<=T(x)<=b]
    R=win("RATE",g0,g1); A=win("ATT",g0,g1); C=win("CTUN",g0,g1); RC=win("RCIN",g0,g1)
    yaw_des=[x.YDes for x in R]; yaw=[x.Y for x in R]
    # yaw-rate tracking
    err=[a-b for a,b in zip(yaw_des,yaw)]
    # pilot stick activity during GUIDED: deviation from first sample in GUIDED (channels 1-4)
    base=[RC[0].C1,RC[0].C2,RC[0].C3,RC[0].C4]
    dev=lambda x:max(abs(x.C1-base[0]),abs(x.C2-base[1]),abs(x.C4-base[3]))
    thr=[x.C3 for x in RC]
    maxdev=max(dev(x) for x in RC)
    # RC activity windows >50us from baseline
    act=[round(T(x)-g0,1) for x in RC if dev(x)>50]
    altg=[x.Alt for x in C]; cl=[x.CRt for x in C]
    pre=win("CTUN",g0-5,g0)
    res=dict(guided_s=round(g1-g0,1),armed_s=round(dis-arm,1),takeoff_to_guided_s=round(g0-arm,1),
      guided_to_land_s=round(land-g1,1),
      yaw_rate_des_max_degs=round(max(abs(v) for v in yaw_des),2),yaw_rate_act_max_degs=round(max(abs(v) for v in yaw),2),
      yaw_rate_rms_err_degs=round((sum(e*e for e in err)/len(err))**.5,2),
      frac_time_yawdes_nonzero=round(sum(1 for v in yaw_des if abs(v)>0.5)/len(yaw_des),3),
      alt_in_guided_min_max_m=(round(min(altg),2),round(max(altg),2)),max_abs_climb_ms=round(max(abs(v) for v in cl),2),
      rc_max_dev_us_ch124=maxdev,rc_samples_over50us=len(act),rc_first_last_active_s_after_guided=(act[0],act[-1]) if act else None,
      throttle_ch3_min_max=(min(thr),max(thr)))
    # final descent: last 60 s before land
    tail=lambda k,a,b:win(k,a,b)
    t0=land-60
    cts=tail("CTUN",t0,land); bs=tail("BAT",t0,land); rcs=tail("RCIN",t0,land)
    res["final60s"]=dict(alt_start=round(cts[0].Alt,2),alt_end=round(cts[-1].Alt,2),
       alt_samples_every10s=[round(x.Alt,1) for x in cts[::100]],
       volt_every10s=[round(x.Volt,2) for x in bs[::100]],
       thr_in_every10s=[x.C3 for x in rcs[::100]], mode_changes=[(round(t-g0,1),mn) for t,mn in modes if t>=t0])
    # last 120 s: when did descent begin (alt falling >0.3 m/s sustained)
    cs=win("CTUN",g1,land)
    res["after_guided_exit"]=dict(alt_at_exit=round(cs[0].Alt,2),alt_at_land=round(cs[-1].Alt,2),min_climbrate=round(min(x.CRt for x in cs),2),
        min_volt_after=round(min(x.Volt for x in win("BAT",g1,land)),2),volt_at_exit=round(win("BAT",g1,g1+1)[0].Volt,2))
    out[lab]=res
print(json.dumps(out,indent=1))
json.dump(out,open("fcu_response_summary.json","w"),indent=1)
