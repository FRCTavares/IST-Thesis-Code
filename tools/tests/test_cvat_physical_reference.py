import copy,hashlib,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"tools"/"analysis"))
import cvat_physical_reference as C

def manifest(n=3):
 rows=[]
 stamps=[1000000000,1040000000,1090000000][:n]
 for i,t in enumerate(stamps):
  rows.append({"cvat_frame_index":i,"source_frame_index":i,"source_timestamp_ns":t,
   "bag_record_timestamp_ns":t+2,"header_timestamp_ns":t,
   "bag_relative_timestamp_ns":t-stamps[0],"t_s":(t-stamps[0])/1e9,
   "media_filename":f"frame_{i:06d}.png","width":640,"height":480})
 return {"manifest_version":C.MV,"sequence_id":"seq","source_bag_path":"bags/source/x",
  "source_bag_name":"x","source_bag_provenance":{"source_image_topic":"/camera/image_raw"},
  "source_width":640,"source_height":480,"coordinate_convention":"source_pixels_historical_pre_p53",
  "coordinate_convention_evidence":"test","evaluation_window":{"start_s":0.0,"end_s":rows[-1]["t_s"]},
  "frame_count":n,"frames":rows}

def config(n=3,state="present_scored",context="distractors_complete",roles=None):
 roles=["target","phys_d001"] if roles is None else roles
 return {"config_version":C.CV,"sequence_id":"seq","annotator":"human","created_date":"2026-08-26",
  "selected_physical_target_label":"black_shirt_person","coordinate_convention_evidence":"test",
  "allow_occluded_geometry":False,"semantic_intervals":[{"start_frame":0,"end_frame":n-1,
  "identity_state":state,"identity_context":context,"required_roles":roles}]}

def xml_text(target_id="91",distractor_id="4",duplicate=False,changed=False,bad=False,occluded=False):
 xbr="700" if bad else "20";second_role="phys_d002" if changed else "target"
 extra=f'''<track id="7" label="person"><box frame="0" outside="0" occluded="0" keyframe="1" xtl="30" ytl="10" xbr="40" ybr="40"><attribute name="physical_ref">target</attribute></box></track>''' if duplicate else ""
 return f'''<annotations><version>1.1</version><meta><task><original_size><width>640</width><height>480</height></original_size></task></meta>
 <track id="{target_id}" label="person">
  <box frame="0" outside="0" occluded="{int(occluded)}" keyframe="1" xtl="10" ytl="10" xbr="{xbr}" ybr="30"><attribute name="physical_ref">target</attribute></box>
  <box frame="2" outside="0" occluded="0" keyframe="1" xtl="20" ytl="20" xbr="30" ybr="40"><attribute name="physical_ref">{second_role}</attribute></box>
 </track>
 <track id="{distractor_id}" label="person">
  <box frame="0" outside="0" occluded="0" keyframe="1" xtl="100" ytl="100" xbr="120" ybr="140"><attribute name="physical_ref">phys_d001</attribute></box>
  <box frame="2" outside="0" occluded="0" keyframe="1" xtl="110" ytl="110" xbr="130" ybr="150"><attribute name="physical_ref">phys_d001</attribute></box>
 </track>{extra}</annotations>'''

def write_inputs(tmp_path,xml=None,cfg=None,m=None):
 m=m or manifest();cfg=cfg or config(len(m["frames"]));mp=tmp_path/"manifest.json";cp=tmp_path/"config.json";xp=tmp_path/"annotations.xml"
 mp.write_text(json.dumps(m));cp.write_text(json.dumps(cfg));xp.write_text(xml or xml_text())
 return xp,mp,cp

def test_manifest_exact_one_to_one_and_timestamp_validation(tmp_path):
 m=manifest();media=tmp_path/"images";media.mkdir()
 for row in m["frames"]:(media/row["media_filename"]).write_bytes(b"x")
 assert C.validate_manifest(m,media)["frame_count"]==3
 assert m["frames"][-1]["t_s"]==pytest.approx(.09)
 broken=copy.deepcopy(m);broken["frames"][1]["source_timestamp_ns"]=m["frames"][0]["source_timestamp_ns"]
 with pytest.raises(C.CvatBridgeError,match="timestamps"):C.validate_manifest(broken)
 broken=copy.deepcopy(m);broken["frames"][1]["cvat_frame_index"]=0
 with pytest.raises(C.CvatBridgeError,match="indices"):C.validate_manifest(broken)
 (media/"frame_000002.png").unlink()
 with pytest.raises(C.CvatBridgeError,match="media"):C.validate_manifest(m,media)

def test_cvat_interpolation_roles_and_numeric_ids_are_not_identity(tmp_path):
 xp,mp,_=write_inputs(tmp_path)
 g=C.geometry(xp,C.load_manifest(mp))
 assert g[1]["target"]==pytest.approx((15,15,25,35))
 assert g[1]["phys_d001"]==pytest.approx((105,105,125,145))
 assert set(g[1])=={"target","phys_d001"}
 assert "91" not in g[1] and "4" not in g[1]

@pytest.mark.parametrize("kwargs,match",[
 ({"duplicate":True},"duplicate role"),({"changed":True},"changes physical role"),
 ({"bad":True},"invalid frame/bbox"),({"occluded":True},"occluded")])
def test_ambiguous_or_invalid_cvat_is_rejected(tmp_path,kwargs,match):
 xp,mp,_=write_inputs(tmp_path,xml=xml_text(**kwargs))
 with pytest.raises(C.CvatBridgeError,match=match):C.geometry(xp,C.load_manifest(mp))

def test_coordinate_transform_must_be_identity(tmp_path):
 x=xml_text().replace("<width>640</width>","<width>320</width>")
 xp,mp,_=write_inputs(tmp_path,xml=x)
 with pytest.raises(C.CvatBridgeError,match="transform"):C.geometry(xp,C.load_manifest(mp))

def test_missing_role_mapping_is_rejected(tmp_path):
 x=xml_text().replace("<attribute name=\"physical_ref\">target</attribute>","",1)
 xp,mp,_=write_inputs(tmp_path,xml=x)
 with pytest.raises(C.CvatBridgeError,match="physical_ref"):C.geometry(xp,C.load_manifest(mp))

def test_semantic_state_sidecar_supports_absent_unavailable_and_gap():
 m=manifest()
 for state in ("absent","present_reference_unavailable","reference_gap"):
  cfg=config(state=state,context=None,roles=[])
  assert all(s[0]==state for s in C.semantics(cfg,m))
 bad=config();bad["semantic_intervals"][0]["identity_state"]="unknown"
 with pytest.raises(C.CvatBridgeError,match="unsupported"):C.semantics(bad,m)

def test_conversion_outputs_per_frame_v2_and_preserves_inputs(tmp_path):
 xp,mp,cp=write_inputs(tmp_path);out=tmp_path/"out.json"
 before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xp,mp,cp)}
 summary=C.convert(xp,mp,cp,out)
 after={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xp,mp,cp)}
 assert before==after
 data=json.loads(out.read_text())
 assert len(data["samples"])==3 and summary["converted_samples"]==3
 assert data["samples"][0]["interpolate_from_previous"] is False
 assert data["samples"][1]["interpolate_from_previous"] is True
 assert data["samples"][-1]["t_s"]==pytest.approx(.09)
 assert summary["right_boundary_anchor_present"] is True
 assert data["samples"][1]["distractors"][0]["person_ref"]=="phys_d001"
 text=out.read_text()
 assert '"91"' not in text and '"4"' not in text

def test_conversion_rejects_missing_role_and_does_not_write(tmp_path):
 x=xml_text().replace('outside="0" occluded="0" keyframe="1" xtl="100"','outside="1" occluded="0" keyframe="1" xtl="100"',1)
 xp,mp,cp=write_inputs(tmp_path,xml=x);out=tmp_path/"out.json"
 with pytest.raises(C.CvatBridgeError,match="role mismatch"):C.convert(xp,mp,cp,out)
 assert not out.exists()

def test_conversion_does_not_mutate_existing_human_artifact(tmp_path):
 canonical=tmp_path/"seq01_clean.json";canonical.write_text('{"human":"untouched"}\n')
 before=hashlib.sha256(canonical.read_bytes()).hexdigest()
 xp,mp,cp=write_inputs(tmp_path);C.convert(xp,mp,cp,tmp_path/"different-output.json")
 assert hashlib.sha256(canonical.read_bytes()).hexdigest()==before

def test_validate_command_reconciles_provenance(tmp_path):
 xp,mp,cp=write_inputs(tmp_path);out=tmp_path/"out.json";C.convert(xp,mp,cp,out)
 assert C.validate_against(out,mp)["converted_samples"]==3
 bad=manifest();bad["sequence_id"]="other";(tmp_path/"bad.json").write_text(json.dumps(bad))
 with pytest.raises(C.CvatBridgeError,match="sequence"):C.validate_against(out,tmp_path/"bad.json")


def image_xml(n=3, *, duplicate=False, missing=False, missing_ref=False,
              label="person", wrong_name=False, wrong_dimensions=False,
              bad_bbox=False, incomplete=False, unsupported_shape=False):
 images=[]
 for frame in range(n-(1 if incomplete else 0)):
  name=f"frame_{frame:06d}.png"
  if wrong_name and frame==1: name="frame_000002.png"
  width="320" if wrong_dimensions and frame==1 else "640"
  children=[]
  roles=["target","phys_d001"]
  if missing and frame==1: roles=["target"]
  if duplicate and frame==1: roles=["target","phys_d001","target"]
  for physical_role in roles:
   attribute="" if missing_ref and frame==1 and physical_role=="target" else f'<attribute name="physical_ref">{physical_role}</attribute>'
   xbr="700" if bad_bbox and frame==1 and physical_role=="target" else ("20" if physical_role=="target" else "120")
   x1="10" if physical_role=="target" else "100"
   children.append(f'<box label="{label}" source="manual" occluded="0" xtl="{x1}" ytl="10" xbr="{xbr}" ybr="40" z_order="0">{attribute}</box>')
  if unsupported_shape and frame==1: children.append('<polygon label="person" points="1,1;2,2;3,3"/>')
  images.append(f'<image id="{frame}" name="{name}" width="{width}" height="480">{"".join(children)}</image>')
 return f'<annotations><version>1.1</version>{"".join(images)}</annotations>'

def test_valid_image_sequence_export_maps_manifest_frames_and_roles(tmp_path):
 xp,mp,_=write_inputs(tmp_path,xml=image_xml())
 geometry=C.geometry(xp,C.load_manifest(mp))
 assert sorted(geometry)==[0,1,2]
 assert geometry[0]["target"]==pytest.approx((10,10,20,40))
 assert geometry[2]["phys_d001"]==pytest.approx((100,10,120,40))

def test_image_sequence_conversion_uses_exact_manifest_timestamps(tmp_path):
 xp,mp,cp=write_inputs(tmp_path,xml=image_xml());out=tmp_path/"image-v2.json"
 result=C.convert(xp,mp,cp,out);data=json.loads(out.read_text())
 assert result["converted_samples"]==3
 assert [sample["t_s"] for sample in data["samples"]]==pytest.approx([0,.04,.09])
 assert data["samples"][-1]["interpolate_from_previous"] is True

@pytest.mark.parametrize("kwargs,match",[
 ({"duplicate":True},"duplicate physical role"),
 ({"missing_ref":True},"physical_ref"),
 ({"label":"car"},"unsupported label"),
 ({"wrong_name":True},"frame/name mismatch"),
 ({"wrong_dimensions":True},"dimensions mismatch"),
 ({"bad_bbox":True},"invalid frame/bbox"),
 ({"incomplete":True},"incomplete image frame coverage"),
 ({"unsupported_shape":True},"unsupported image shape"),
])
def test_invalid_image_sequence_exports_are_rejected(tmp_path,kwargs,match):
 xp,mp,_=write_inputs(tmp_path,xml=image_xml(**kwargs))
 with pytest.raises(C.CvatBridgeError,match=match):
  C.geometry(xp,C.load_manifest(mp))

def test_image_sequence_missing_present_scored_role_is_rejected(tmp_path):
 xp,mp,cp=write_inputs(tmp_path,xml=image_xml(missing=True));out=tmp_path/"out.json"
 with pytest.raises(C.CvatBridgeError,match="frame 1 role mismatch"):
  C.convert(xp,mp,cp,out)
 assert not out.exists()

def test_existing_track_representation_remains_supported(tmp_path):
 xp,mp,_=write_inputs(tmp_path,xml=xml_text(target_id="991",distractor_id="882"))
 geometry=C.geometry(xp,C.load_manifest(mp))
 assert geometry[1]["target"]==pytest.approx((15,15,25,35))
 assert geometry[1]["phys_d001"]==pytest.approx((105,105,125,145))
 assert "991" not in geometry[1] and "882" not in geometry[1]

def test_ordered_image_task_config_uses_validated_export_format():
 task=C.cvat_task_config(["target","phys_d001"])
 assert task["export"]=="CVAT for images 1.1"
 assert task["supported_alternate_export"]=="CVAT for video 1.1 native track representation"
 assert "physical_ref only" in task["identity_authority"]
 assert "never nominal FPS" in task["timestamp_authority"]
 assert task["review_authority"]=="human review remains authoritative"
