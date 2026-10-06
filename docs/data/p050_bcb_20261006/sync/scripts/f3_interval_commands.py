import json,numpy as np,os,datetime
H=os.path.expanduser("~"); D=H+"/flight_evidence_20261006_dataflash/f3_sync/"
ex=json.load(open(D+"f3_wrong_person_exposure.json")); C=np.load(D+"cmd_launchrel.npy")
L=datetime.datetime.fromisoformat("2026-10-02T14:59:46.825260970+00:00").timestamp()
U=lambda s:datetime.datetime.fromtimestamp(L+s,datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-4]
ct=C[:,0]; dt=np.minimum(np.diff(ct,append=ct[-1]),0.5); nz=(np.abs(C[:,1])>1e-6)|(np.abs(C[:,2])>1e-6)
for key in ("/target_memory_mars|0.94","/target_memory_mars|1.02","/target_memory_mars|1.10"):
    n,nr,tot,nzt,nzf,ints=ex[key]; print(key,"frames",n,"nonzero s",nzt)
    for a,b in ints:
        m=(ct>=a)&(ct<b); w=np.abs(C[m,2]); v=np.abs(C[m,1])
        print("  %s-%s (%.2fs) nonzero cmd %.2fs  mean|wz| %.3f max|wz| %.3f max|vx| %.3f"%(U(a),U(b),b-a,float((dt[m]*nz[m]).sum()),float(w.mean()) if len(w) else 0,float(w.max()) if len(w) else 0,float(v.max()) if len(v) else 0))
