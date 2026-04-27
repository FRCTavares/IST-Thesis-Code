import json
import os

files = {
    "direct": "reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_direct_r1.json",
    "appsrccap": "reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_appsrccap_r2.json",
    "legacy": "reports/timing/live_post_refactor/legacy_r3.json"
}

def get_timing_val(data, metric, key):
    # Statistics are under "metrics" -> "/timing" (or other topics)
    m_sect = data.get("metrics", {})
    for topic in ["/timing", "/timing_target", "/timing_tracker"]:
        val = m_sect.get(topic, {}).get(metric, {}).get(key)
        if val is not None:
            return val
    return 0

results = {}
for name, path in files.items():
    if not os.path.exists(path):
        print(f"File not found: {path}")
        continue
    with open(path, 'r') as f:
        d = json.load(f)
        results[name] = d
        print(f"--- {name} ---")
        hz = d.get("topics", {}).get("/timing", {}).get("hz", 0)
        print(f"/timing hz: {hz:.2f}")
        
        for m in ["e2e_det_ms", "container_queue_ms", "infer_ms", "pub_dt_ms"]:
            p50 = get_timing_val(d, m, "p50")
            p95 = get_timing_val(d, m, "p95")
            print(f"{m} p50/p95: {p50:.2f}/{p95:.2f}")
            
        ds = d.get("detection_stream", {})
        dpm = ds.get("detections_per_msg", {})
        print(f"detection_stream: mean={dpm.get('mean', 0):.4f}, zero_ratio={dpm.get('zero_ratio', 0):.4f}")
        
        cc = d.get("cadence_consistency", {})
        print(f"cadence_consistency: relative_delta={cc.get('relative_delta', 0):.4f}, within_tolerance={cc.get('within_tolerance', 0)}")
        
        print(f"health.score: {d.get('health', {}).get('score', 0):.4f}")
        print()

def print_delta(n1, n2):
    d1 = results.get(n1)
    d2 = results.get(n2)
    if not d1 or not d2: return
    print(f"--- Delta ({n1} - {n2}) ---")
    
    for m in ["e2e_det_ms", "container_queue_ms", "infer_ms", "pub_dt_ms"]:
        v1 = get_timing_val(d1, m, "p95")
        v2 = get_timing_val(d2, m, "p95")
        print(f"{m.replace('_ms','')}_p95: {v1 - v2:.2f}")
    
    hz1 = d1.get("topics", {}).get("/timing", {}).get("hz", 0)
    hz2 = d2.get("topics", {}).get("/timing", {}).get("hz", 0)
    print(f"hz: {hz1 - hz2:.2f}")
    
    dm1 = d1.get("detection_stream", {}).get("detections_per_msg", {}).get("mean", 0)
    dm2 = d2.get("detection_stream", {}).get("detections_per_msg", {}).get("mean", 0)
    print(f"det_mean: {dm1 - dm2:.4f}")
    
    zr1 = d1.get("detection_stream", {}).get("detections_per_msg", {}).get("zero_ratio", 0)
    zr2 = d2.get("detection_stream", {}).get("detections_per_msg", {}).get("zero_ratio", 0)
    print(f"zero_ratio: {zr1 - zr2:.4f}")
    print()

print_delta("direct", "appsrccap")
print_delta("direct", "legacy")
