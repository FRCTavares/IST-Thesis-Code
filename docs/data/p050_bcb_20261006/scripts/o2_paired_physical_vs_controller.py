import json,datetime,glob,os
H=os.path.expanduser("~")
tl=json.load(open(H+"/flight_evidence_20261006_dataflash/bcb/bcb_timeline.json"))
def utc(s): return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
meta={}
for lab,bag in (("F1","2026-10-02__15-37-40__video__bcb_baseline_a"),("F2","2026-10-02__15-49-03__video__bcb_candidate"),("F3","2026-10-02__15-58-43__video__bcb_baseline_b")):
    m=json.load(open(H+"/Desktop/Thesis-Code/bags/live_camera/"+bag+"/run_metadata.json")); meta[lab]=m["visual"]["started_at_utc"] if "visual" in m else None
    print(lab,"visual.started_at_utc",meta[lab])
# launch UTC derived from target_selected UTC and operator_target_selected_relative_launch_s
rel={"F1":(175.93409895896912,"2026-10-02T14:41:14.701650Z"),"F2":(158.18742394447327,"2026-10-02T14:52:25.526610Z")}
absent={"F1":(241.74,256.98),"F2":(263.56,273.12)}   # estimated source interval (launch-relative), existing evaluations, fitted offsets 0.74 / 0.32 s
out={}
for lab in ("F1","F2"):
    L=utc(rel[lab][1])-rel[lab][0]
    gaps=[g for g in tl[lab]["guided_window"]["gaps"] if g["dur"]>=10]
    g=gaps[0]; gs,ge=g["start"]-L,g["end"]-L; a0,a1=absent[lab]
    out[lab]=dict(launch_utc=datetime.datetime.fromtimestamp(L,datetime.timezone.utc).isoformat(),controller_gap_launch_s=[round(gs,2),round(ge,2)],controller_gap_s=round(ge-gs,2),
      physical_absence_launch_s=[a0,a1],physical_absence_s=round(a1-a0,2),
      controller_loss_minus_physical_loss_s=round(gs-a0,2),controller_return_minus_physical_return_s=round(ge-a1,2),
      frozen_10s_horizon=dict(person_returned_within_10s=(a1-a0)<=10,controller_trusted_within_10s=(ge-a0)<=10),
      recovery_in_gap=tl[lab]["guided_window"].get("recovery_activations"))
print(json.dumps(out,indent=1))
json.dump(out,open(H+"/flight_evidence_20261006_dataflash/bcb/o2_paired_physical_vs_controller.json","w"),indent=1)
