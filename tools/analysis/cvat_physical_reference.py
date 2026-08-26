#!/usr/bin/env python3
"""Exact-frame CVAT bridge for identity-independent physical-reference v2."""
import argparse,csv,hashlib,json,math,subprocess,sys,zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from physical_target_reference_v2 import CONTRACT_VERSION,SCHEMA_VERSION,COORDINATE_CONVENTIONS,load_physical_reference,parse_physical_reference,validate_physical_reference,write_physical_reference
MV="tim_cvat_frame_manifest_v1";CV="tim_cvat_physical_reference_config_v1";PV="tim_cvat_preparation_config_v1";TARGET="target";GAP="reference_gap";ATTR="physical_ref"
class CvatBridgeError(ValueError): pass
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""): h.update(b)
 return h.hexdigest()
def dump(p,x): Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
def role(r):
 import re
 if r!=TARGET and not re.fullmatch(r"phys_d[0-9]{3,}",r): raise CvatBridgeError(f"invalid physical_ref {r!r}")
 return r
def flag(v):
 if str(v).lower() in ("1","true"): return True
 if str(v).lower() in ("0","false"): return False
 raise CvatBridgeError("invalid CVAT boolean")
def validate_manifest(m,media=None):
 rows=m.get("frames",[]);n=len(rows)
 if m.get("manifest_version")!=MV or not rows or n!=m.get("frame_count"): raise CvatBridgeError("invalid manifest/count")
 stamps=[int(r["source_timestamp_ns"]) for r in rows]
 if [r["cvat_frame_index"] for r in rows]!=list(range(n)) or [r["source_frame_index"] for r in rows]!=list(range(n)): raise CvatBridgeError("frame indices not unique contiguous")
 if any(b<=a for a,b in zip(stamps,stamps[1:])): raise CvatBridgeError("timestamps not strictly increasing")
 for i,r in enumerate(rows):
  rel=stamps[i]-stamps[0]
  if r["media_filename"]!=f"frame_{i:06d}.png" or (r["width"],r["height"])!=(m["source_width"],m["source_height"]): raise CvatBridgeError("media metadata mismatch")
  if r["bag_relative_timestamp_ns"]!=rel or not math.isclose(r["t_s"],rel/1e9,abs_tol=5e-13): raise CvatBridgeError("timestamp mismatch")
 if not math.isclose(m["evaluation_window"]["end_s"],rows[-1]["t_s"],abs_tol=5e-13): raise CvatBridgeError("right boundary mismatch")
 if media and [p.name for p in sorted(Path(media).glob("frame_*.png"))]!=[r["media_filename"] for r in rows]: raise CvatBridgeError("media count/order mismatch")
 return m
def load_manifest(p,media=None): return validate_manifest(json.loads(Path(p).read_text()),media)
def cvat_task_config(roles,task_name=None,frame_count=None):
 out={"task_type":"ordered image sequence/interpolation","sorting":"lexicographical","frame_step":1,"resize":"none; exact source pixels","label":"person","attribute":{"name":ATTR,"type":"select","mutable":False,"values":roles},"export":"CVAT for images 1.1","supported_alternate_export":"CVAT for video 1.1 native track representation","identity_authority":"physical_ref only; never numeric CVAT IDs or drawing order","timestamp_authority":"frame_manifest.json exact source timestamps; never nominal FPS","review_authority":"human review remains authoritative"}
 if task_name is not None:out["task_name"]=task_name
 if frame_count is not None:out["frame_count"]=frame_count
 return out

def preparation_config(path):
 x=json.loads(Path(path).read_text())
 if x.get("preparation_config_version")!=PV: raise CvatBridgeError("invalid preparation config version")
 required=("sequence_id","source_bag_path","source_image_topic","source_width","source_height","coordinate_convention","coordinate_convention_evidence","selected_physical_target_label","annotator","allowed_roles")
 if any(k not in x for k in required): raise CvatBridgeError("preparation config missing required field")
 roles=[role(r) for r in x["allowed_roles"]]
 if not roles or roles[0]!=TARGET or len(roles)!=len(set(roles)): raise CvatBridgeError("allowed_roles must start with unique target")
 if not all(str(x[k]).strip() for k in ("sequence_id","source_bag_path","source_image_topic","coordinate_convention","coordinate_convention_evidence","selected_physical_target_label","annotator")): raise CvatBridgeError("preparation metadata must be non-empty")
 if not isinstance(x["source_width"],int) or not isinstance(x["source_height"],int) or x["source_width"]<=0 or x["source_height"]<=0: raise CvatBridgeError("invalid preparation dimensions")
 if x["coordinate_convention"] not in COORDINATE_CONVENTIONS: raise CvatBridgeError("invalid preparation coordinate convention")
 return x,roles

def seed(path,m,refp,roles):
 s=load_physical_reference(refp).samples[0];boxes={TARGET:s.target_bbox_xyxy}|{d.person_ref:d.bbox_xyxy for d in s.distractors}
 if s.t_s!=0 or set(boxes)!=set(roles): raise CvatBridgeError("seed mismatch")
 root=ET.Element("annotations");ET.SubElement(root,"version").text="1.1";task=ET.SubElement(ET.SubElement(root,"meta"),"task")
 ET.SubElement(task,"mode").text="interpolation";size=ET.SubElement(task,"original_size");ET.SubElement(size,"width").text=str(m["source_width"]);ET.SubElement(size,"height").text=str(m["source_height"])
 for tid,r in enumerate(roles):
  tr=ET.SubElement(root,"track",{"id":str(tid),"label":"person","source":"manual"})
  for frame,out in ((0,0),(1,1)):
   x1,y1,x2,y2=boxes[r];b=ET.SubElement(tr,"box",{"frame":str(frame),"outside":str(out),"occluded":"0","keyframe":"1","xtl":str(x1),"ytl":str(y1),"xbr":str(x2),"ybr":str(y2),"z_order":"0"});ET.SubElement(b,"attribute",{"name":ATTR}).text=r
 ET.indent(root);ET.ElementTree(root).write(path,encoding="utf-8",xml_declaration=True)
def prepare(bag,refp,out,prepp=None):
 import cv2,rosbag2_py
 from cv_bridge import CvBridge
 from rclpy.serialization import deserialize_message
 from rosidl_runtime_py.utilities import get_message
 from types import SimpleNamespace
 if (refp is None)==(prepp is None): raise CvatBridgeError("choose exactly one reference or preparation config")
 if refp is not None:
  ref=load_physical_reference(refp);p=ref.provenance;roles=[TARGET]+[d.person_ref for d in ref.samples[0].distractors];seed_ref=refp;prep=None
 else:
  prep,roles=preparation_config(prepp);p=SimpleNamespace(**prep);seed_ref=None
 bag=Path(bag).resolve();out=Path(out);root=Path(__file__).resolve().parents[2]
 if (root/p.source_bag_path).resolve()!=bag: raise CvatBridgeError("bag path differs from preparation/reference provenance")
 if out.exists() and any(out.iterdir()): raise CvatBridgeError("output must be empty/absent")
 images=out/"images";images.mkdir(parents=True,exist_ok=True);rd=rosbag2_py.SequentialReader()
 rd.open(rosbag2_py.StorageOptions(uri=str(bag),storage_id="mcap"),rosbag2_py.ConverterOptions(input_serialization_format="cdr",output_serialization_format="cdr"))
 types={x.name:x.type for x in rd.get_all_topics_and_types()};cls=get_message(types[p.source_image_topic]);bridge=CvBridge();rows=[];first=prev=None
 while rd.has_next():
  topic,raw,record=rd.read_next()
  if topic!=p.source_image_topic: continue
  msg=deserialize_message(raw,cls);st=msg.header.stamp;header=int(st.sec)*10**9+int(st.nanosec);ts=header or int(record)
  if prev is not None and ts<=prev: raise CvatBridgeError("timestamps not increasing")
  first=ts if first is None else first;prev=ts;im=bridge.imgmsg_to_cv2(msg,desired_encoding="bgr8");h,w=im.shape[:2]
  if (w,h)!=(p.source_width,p.source_height): raise CvatBridgeError("resolution mismatch")
  i=len(rows);name=f"frame_{i:06d}.png"
  if not cv2.imwrite(str(images/name),im,[cv2.IMWRITE_PNG_COMPRESSION,3]): raise CvatBridgeError("PNG write failed")
  rel=ts-first;rows.append({"cvat_frame_index":i,"source_frame_index":i,"source_timestamp_ns":ts,"bag_record_timestamp_ns":int(record),"header_timestamp_ns":header or None,"bag_relative_timestamp_ns":rel,"t_s":rel/1e9,"media_filename":name,"width":w,"height":h})
 head=subprocess.run(["git","rev-parse","HEAD"],cwd=Path(__file__).resolve().parents[2],text=True,check=True,stdout=subprocess.PIPE).stdout.strip()
 m={"manifest_version":MV,"sequence_id":p.sequence_id,"source_bag_path":p.source_bag_path,"source_bag_resolved_path":str(bag),"source_bag_name":bag.name,"source_bag_provenance":{"metadata_yaml_sha256":sha(bag/"metadata.yaml"),"storage_id":"mcap","source_image_topic":p.source_image_topic},"source_width":p.source_width,"source_height":p.source_height,"coordinate_convention":p.coordinate_convention,"coordinate_convention_evidence":p.coordinate_convention_evidence,"evaluation_window":{"start_s":0.0,"end_s":rows[-1]["t_s"]},"frame_count":len(rows),"extraction":{"tool":"tools/analysis/cvat_physical_reference.py","version":"1","repository_head":head,"media":"lossless source-resolution PNG, no resize","timestamp":"positive Image.header.stamp else bag record"},"frames":rows}
 validate_manifest(m,images)
 if refp is not None and not math.isclose(rows[-1]["t_s"],p.evaluation_window.end_s,abs_tol=5e-10): raise CvatBridgeError("bag/reference end mismatch")
 dump(out/"frame_manifest.json",m)
 with (out/"frame_manifest.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 if refp is not None:
  cfg={"config_version":CV,"sequence_id":p.sequence_id,"annotator":p.annotator,"created_date":str(date.today()),"selected_physical_target_label":p.selected_physical_target_label,"coordinate_convention_evidence":p.coordinate_convention_evidence,"required_roles":roles,"allow_occluded_geometry":False,"semantic_intervals":[{"start_frame":0,"end_frame":len(rows)-1,"identity_state":"present_scored","identity_context":"distractors_complete","required_roles":roles,"human_assertion":"Seq01 only; confirm during complete CVAT review"}]}
 else:
  cfg={"config_version":CV,"sequence_id":p.sequence_id,"annotator":p.annotator,"created_date":str(date.today()),"selected_physical_target_label":p.selected_physical_target_label,"coordinate_convention_evidence":p.coordinate_convention_evidence,"allowed_roles":roles,"allow_occluded_geometry":False,"preparation_status":"human_review_required","conversion_blocker":"Populate complete, human-validated semantic_intervals and required_roles after CVAT review; conversion intentionally fails while this list is empty.","semantic_intervals":[]}
  dump(out/"preparation_config.json",prep)
 dump(out/"conversion_config.json",cfg)
 if seed_ref is not None: seed(out/"seed_annotations.xml",m,seed_ref,roles)
 task=cvat_task_config(roles,p.sequence_id,len(rows));task["seed_annotations"]="seed_annotations.xml" if seed_ref is not None else "none; establish every physical_ref manually in CVAT";task["media_archive"]=f"{p.sequence_id}_cvat_images.zip";dump(out/"cvat_task.json",task)
 arc=out/f"{p.sequence_id}_cvat_images.zip"
 with zipfile.ZipFile(arc,"w",zipfile.ZIP_DEFLATED,compresslevel=1) as z:
  for r in rows:z.write(images/r["media_filename"],r["media_filename"])
 names=["frame_manifest.json","frame_manifest.csv","conversion_config.json","cvat_task.json",arc.name]
 if seed_ref is not None:names.append("seed_annotations.xml")
 else:names.append("preparation_config.json")
 sums={x:sha(out/x) for x in names};dump(out/"SHA256SUMS.json",sums)
 return {"archive_path":str(arc),"archive_size_bytes":arc.stat().st_size,"archive_sha256":sums[arc.name],"frame_count":len(rows),"dimensions":[p.source_width,p.source_height],"first_timestamp_ns":rows[0]["source_timestamp_ns"],"final_timestamp_ns":rows[-1]["source_timestamp_ns"],"evaluation_end_s":rows[-1]["t_s"],"seed_annotations_path":str(out/"seed_annotations.xml") if seed_ref is not None else None}
def xml(path):
 raw=Path(path).read_bytes()
 if zipfile.is_zipfile(path):
  with zipfile.ZipFile(path) as z:
   names=[n for n in z.namelist() if n.endswith("annotations.xml")]
   if len(names)!=1: raise CvatBridgeError("ZIP needs one annotations.xml")
   root=ET.fromstring(z.read(names[0]))
 else: root=ET.fromstring(raw)
 return root,hashlib.sha256(raw).hexdigest()
def _track_geometry(root,m,allow=False):
 w,h=m["source_width"],m["source_height"];xw=root.findtext("./meta/task/original_size/width");xh=root.findtext("./meta/task/original_size/height")
 if xw and (int(xw),int(xh))!=(w,h): raise CvatBridgeError("coordinate transform unproven")
 out={i:{} for i in range(m["frame_count"])};owners={}
 for tr in root.findall("./track"):
  tid=tr.get("id");bs=[]
  if tr.get("label")!="person": raise CvatBridgeError("unsupported label")
  for b in tr.findall("./box"):
   vals={(a.text or "").strip() for a in tr.findall(f"./attribute[@name='{ATTR}']")+b.findall(f"./attribute[@name='{ATTR}']") if (a.text or "").strip()}
   if len(vals)!=1: raise CvatBridgeError("missing/changed physical_ref")
   r=role(vals.pop());f=int(b.get("frame"));bb=tuple(float(b.get(k)) for k in ("xtl","ytl","xbr","ybr"));x1,y1,x2,y2=bb
   if not 0<=f<m["frame_count"] or not(0<=x1<x2<=w and 0<=y1<y2<=h): raise CvatBridgeError("invalid frame/bbox")
   bs.append((f,r,bb,flag(b.get("outside")),flag(b.get("occluded"))))
  rs={b[1] for b in bs}
  if len(rs)!=1: raise CvatBridgeError("track changes physical role")
  r=next(iter(rs))
  if r in owners: raise CvatBridgeError("duplicate role")
  owners[r]=tid;bs.sort()
  for j,a in enumerate(bs):
   b=bs[j+1] if j+1<len(bs) else None
   if a[3]: continue
   if a[4] and not allow: raise CvatBridgeError("occluded geometry needs explicit approval")
   for f in range(a[0],b[0] if b else m["frame_count"]):
    q=(f-a[0])/(b[0]-a[0]) if b and not b[3] else 0
    out[f][r]=tuple(x+q*(y-x) for x,y in zip(a[2],b[2] if b else a[2]))
 return out

def _image_geometry(root,m,allow=False):
 images=root.findall("./image");rows=m["frames"];width=m["source_width"];height=m["source_height"]
 if len(images)!=len(rows): raise CvatBridgeError(f"incomplete image frame coverage: export has {len(images)}, manifest has {len(rows)}")
 by_frame={}
 for image in images:
  try: frame=int(image.get("id",""))
  except (TypeError,ValueError) as exc: raise CvatBridgeError("invalid CVAT image id") from exc
  if frame in by_frame: raise CvatBridgeError(f"duplicate CVAT image frame {frame}")
  if not 0<=frame<len(rows): raise CvatBridgeError(f"CVAT image frame {frame} outside manifest")
  row=rows[frame]
  if image.get("name")!=row["media_filename"]: raise CvatBridgeError(f"image frame/name mismatch at {frame}")
  try: image_size=(int(image.get("width","")),int(image.get("height","")))
  except (TypeError,ValueError) as exc: raise CvatBridgeError(f"invalid image dimensions at frame {frame}") from exc
  if image_size!=(row["width"],row["height"]) or image_size!=(width,height): raise CvatBridgeError(f"image dimensions mismatch at frame {frame}")
  unsupported=[child.tag for child in image if child.tag!="box"]
  if unsupported: raise CvatBridgeError(f"unsupported image shape at frame {frame}: {unsupported[0]}")
  frame_geometry={}
  for box in image.findall("./box"):
   if box.get("label")!="person": raise CvatBridgeError(f"unsupported label at frame {frame}")
   attrs=[(a.text or "").strip() for a in box.findall(f"./attribute[@name='{ATTR}']")]
   if len(attrs)!=1 or not attrs[0]: raise CvatBridgeError(f"missing or duplicate physical_ref at frame {frame}")
   physical_role=role(attrs[0])
   if physical_role in frame_geometry: raise CvatBridgeError(f"duplicate physical role {physical_role} at frame {frame}")
   try: bbox=tuple(float(box.get(k,"")) for k in ("xtl","ytl","xbr","ybr"))
   except (TypeError,ValueError) as exc: raise CvatBridgeError(f"malformed bbox at frame {frame}") from exc
   x1,y1,x2,y2=bbox
   if any(not math.isfinite(v) for v in bbox) or not(0<=x1<x2<=width and 0<=y1<y2<=height): raise CvatBridgeError(f"invalid frame/bbox at frame {frame}")
   if flag(box.get("occluded","0")) and not allow: raise CvatBridgeError("occluded geometry needs explicit approval")
   frame_geometry[physical_role]=bbox
  by_frame[frame]=frame_geometry
 if sorted(by_frame)!=list(range(len(rows))): raise CvatBridgeError("image frames must be unique contiguous and match the manifest")
 return {frame:by_frame[frame] for frame in range(len(rows))}

def geometry(path,m,allow=False):
 root,_=xml(path)
 if root.findall("./track"): return _track_geometry(root,m,allow)
 if root.findall("./image"): return _image_geometry(root,m,allow)
 raise CvatBridgeError("no supported CVAT track or image annotations")
def semantics(cfg,m):
 if cfg.get("config_version")!=CV or cfg.get("sequence_id")!=m["sequence_id"]: raise CvatBridgeError("invalid config")
 out=[None]*m["frame_count"]
 for it in cfg["semantic_intervals"]:
  st=it["identity_state"];ct=it.get("identity_context");rs=[role(r) for r in it.get("required_roles",[])]
  if st not in ("present_scored","absent","present_reference_unavailable",GAP): raise CvatBridgeError("unsupported state")
  if st=="present_scored" and (ct not in ("target_only","distractors_complete") or TARGET not in rs): raise CvatBridgeError("present state needs context/roles")
  if st!="present_scored" and (ct is not None or rs): raise CvatBridgeError("non-present state cannot imply geometry")
  for i in range(it["start_frame"],it["end_frame"]+1):
   if not 0<=i<len(out) or out[i]: raise CvatBridgeError("interval overlap/range")
   out[i]=(st,ct,rs)
 if any(x is None for x in out): raise CvatBridgeError("semantic config must cover all frames")
 return out
def summary(a,m):
 validate_physical_reference(a);present=[s for s in a.samples if s.identity_state=="present_scored"];counts={}
 for s in present:
  counts[TARGET]=counts.get(TARGET,0)+1
  for d in s.distractors: counts[d.person_ref]=counts.get(d.person_ref,0)+1
 return {"manifest_frames":m["frame_count"],"converted_samples":len(a.samples),"present_scored_samples":len(present),"missing_frames":m["frame_count"]-len(a.samples),"role_frame_coverage":counts,"target_coverage_duration_s":m["evaluation_window"]["end_s"] if len(present)==m["frame_count"] else None,"first_timestamp_s":a.samples[0].t_s,"final_timestamp_s":a.samples[-1].t_s,"evaluation_window":m["evaluation_window"],"right_boundary_anchor_present":math.isclose(a.samples[-1].t_s,m["evaluation_window"]["end_s"],abs_tol=5e-13)}
def convert(export,manifest,config,output):
 m=load_manifest(manifest);raw=Path(config).read_bytes();cfg=json.loads(raw);ss=semantics(cfg,m);gg=geometry(export,m,cfg.get("allow_occluded_geometry",False));_,esh=xml(export);samples=[];prev=None
 for i,(row,s) in enumerate(zip(m["frames"],ss)):
  st,ct,rs=s
  if st==GAP: prev=None;continue
  if st=="present_scored":
   if set(gg[i])!=set(rs): raise CvatBridgeError(f"frame {i} role mismatch; no guessing")
   sample={"t_s":row["t_s"],"identity_state":st,"identity_context":ct,"target_bbox_xyxy":list(gg[i][TARGET]),"distractors":[{"person_ref":r,"bbox_xyxy":list(gg[i][r])} for r in sorted(set(rs)-{TARGET})],"interpolate_from_previous":bool(prev and prev[0]==i-1 and prev[1]["identity_state"]=="present_scored" and prev[1]["identity_context"]==ct and {d["person_ref"] for d in prev[1]["distractors"]}==set(rs)-{TARGET}),"notes":"CVAT-reviewed frame via exact manifest"}
  else:
   if gg[i]: raise CvatBridgeError("state/geometry conflict")
   sample={"t_s":row["t_s"],"identity_state":st,"identity_context":None,"target_bbox_xyxy":None,"distractors":[],"interpolate_from_previous":False,"notes":"explicit sidecar state"}
  samples.append(sample);prev=(i,sample)
 p={"schema_version":SCHEMA_VERSION,"contract_version":CONTRACT_VERSION,"sequence_id":m["sequence_id"],"source_bag_name":m["source_bag_name"],"source_bag_path":m["source_bag_path"],"source_image_topic":m["source_bag_provenance"]["source_image_topic"],"source_width":m["source_width"],"source_height":m["source_height"],"coordinate_convention":m["coordinate_convention"],"coordinate_convention_evidence":cfg["coordinate_convention_evidence"],"selected_physical_target_label":cfg["selected_physical_target_label"],"annotator":cfg["annotator"],"created_date":cfg["created_date"],"evaluation_window":m["evaluation_window"],"notes":f"Human-reviewed CVAT annotations; numeric IDs discarded. Export SHA-256 {esh}; config SHA-256 {hashlib.sha256(raw).hexdigest()}."}
 a=parse_physical_reference({"provenance":p,"samples":samples});validate_physical_reference(a);Path(output).parent.mkdir(parents=True,exist_ok=True);write_physical_reference(output,a);return summary(a,m)
def validate_against(reference,manifest):
 m=load_manifest(manifest);a=load_physical_reference(reference)
 if a.provenance.sequence_id!=m["sequence_id"]: raise CvatBridgeError("reference sequence differs from manifest")
 if (a.provenance.source_width,a.provenance.source_height)!=(m["source_width"],m["source_height"]): raise CvatBridgeError("reference dimensions differ from manifest")
 if not math.isclose(a.provenance.evaluation_window.start_s,m["evaluation_window"]["start_s"],abs_tol=5e-13) or not math.isclose(a.provenance.evaluation_window.end_s,m["evaluation_window"]["end_s"],abs_tol=5e-13): raise CvatBridgeError("reference evaluation window differs from manifest")
 return summary(a,m)
def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest="cmd",required=True)
 a=s.add_parser("prepare");a.add_argument("--bag",type=Path,required=True);g=a.add_mutually_exclusive_group(required=True);g.add_argument("--reference",type=Path);g.add_argument("--preparation-config",type=Path);a.add_argument("--output-dir",type=Path,required=True)
 a=s.add_parser("convert");a.add_argument("--cvat-export",type=Path,required=True);a.add_argument("--manifest",type=Path,required=True);a.add_argument("--config",type=Path,required=True);a.add_argument("--output",type=Path,required=True)
 a=s.add_parser("validate");a.add_argument("--reference",type=Path,required=True);a.add_argument("--manifest",type=Path,required=True)
 x=p.parse_args()
 if x.cmd=="prepare": r=prepare(x.bag,x.reference,x.output_dir,x.preparation_config)
 elif x.cmd=="convert": r=convert(x.cvat_export,x.manifest,x.config,x.output)
 else: r=validate_against(x.reference,x.manifest)
 print(json.dumps(r,indent=2,sort_keys=True))
if __name__=="__main__": main()
