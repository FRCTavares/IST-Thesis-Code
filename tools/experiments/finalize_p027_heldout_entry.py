#!/usr/bin/env python3
"""Propose one ready entry without changing the split or running algorithms."""
from __future__ import annotations

import argparse
import copy
import difflib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/analysis"))
from cvat_physical_reference import load_manifest, validate_against
from p027_handoff import (
    ACTIVE_SPLIT_ID, METADATA_FIELDS, evidence_path, sha256_file,
    source_inventory, validate_ready_entry,
)
from validate_tim_evaluation_split import validate_manifest

SCENARIOS = {
    "h01": "heldout_h01_exit_reentry",
    "h02": "heldout_h02_crossing",
    "h03": "heldout_h03_occlusion_distractor",
}


def propose(split, *, root, scenario, source_path, annotation_path,
            frame_manifest, metadata):
    if split.get("split_id") != ACTIVE_SPLIT_ID:
        raise ValueError("only the active Stage-7 split is supported")
    wanted = SCENARIOS[scenario]
    entries = split["sets"]["final_held_out"]
    matches = [entry for entry in entries if entry["id"] == wanted]
    if len(matches) != 1 or matches[0].get("status") != "reserved_pending_capture":
        raise ValueError("exactly one pending entry required; re-finalization refused")
    if set(metadata) != set(METADATA_FIELDS):
        raise ValueError("metadata must contain exactly: " + ", ".join(METADATA_FIELDS))
    entry = copy.deepcopy(matches[0])
    # Never modify planning fields, scenario membership or bootstrap rules.
    entry.update(metadata)
    entry.update(
        status="ready", source_path=source_path, annotation_path=annotation_path,
        annotation_sha256=sha256_file(evidence_path(root, annotation_path)),
        selected_target_id=0, files=source_inventory(root, source_path),
    )
    validate_ready_entry(entry, root, verify_hashes=True)
    manifest_path = evidence_path(root, frame_manifest)
    manifest = load_manifest(manifest_path)
    validate_against(evidence_path(root, annotation_path), manifest_path)
    if evidence_path(root, manifest["source_bag_path"]).resolve() != evidence_path(root, source_path).resolve():
        raise ValueError("CVAT frame manifest source differs from source_path")
    source = evidence_path(root, source_path)
    if manifest["source_bag_provenance"].get("metadata_yaml_sha256") != sha256_file(source / "metadata.yaml"):
        raise ValueError("CVAT frame manifest source metadata hash mismatch")
    candidate = copy.deepcopy(split)
    candidate["sets"]["final_held_out"] = [
        entry if item["id"] == wanted else item
        for item in candidate["sets"]["final_held_out"]
    ]
    return candidate, entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--split", type=Path, default=ROOT / "docs/data/splits/tim_mars_split_v4.json")
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--annotation-path", required=True)
    parser.add_argument("--frame-manifest", required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--confirm-human-reviewed", action="store_true", required=True)
    args = parser.parse_args()
    try:
        if args.output_dir.exists():
            raise ValueError("proposal output already exists; refusing overwrite")
        if args.output_dir.resolve().is_relative_to(evidence_path(ROOT, args.source_path).resolve()):
            raise ValueError("proposal output must be outside the frozen source bag")
        original = args.split.read_text()
        split = json.loads(original)
        candidate, entry = propose(
            split, root=ROOT, scenario=args.scenario,
            source_path=args.source_path, annotation_path=args.annotation_path,
            frame_manifest=args.frame_manifest,
            metadata=json.loads(args.metadata.read_text()),
        )
        errors = validate_manifest(candidate, repo_root=ROOT, verify_hashes=True,
                                   require_final_ready=False)
        if errors:
            raise ValueError("\n".join(errors))
        # An explicit patch is the only application mechanism. No --apply mode.
        split_relative = args.split.resolve().relative_to(ROOT).as_posix()
        updated = json.dumps(candidate, indent=2) + "\n"
        patch = "".join(difflib.unified_diff(
            original.splitlines(keepends=True), updated.splitlines(keepends=True),
            fromfile="a/" + split_relative, tofile="b/" + split_relative,
        ))
        provenance = {
            "proposal_only": True, "source_split_sha256": sha256_file(args.split),
            "metadata_sha256": sha256_file(args.metadata),
            "frame_manifest_path": args.frame_manifest,
            "frame_manifest_sha256": sha256_file(evidence_path(ROOT, args.frame_manifest)),
            "human_review_confirmed": args.confirm_human_reviewed,
            "tool_commit": subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        }
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for name, value in (("ready-entry.json", entry), ("split.proposed.json", candidate),
                            ("proposal-provenance.json", provenance)):
            (args.output_dir / name).write_text(json.dumps(value, indent=2) + "\n")
        (args.output_dir / "split.patch").write_text(patch)
        print(f"Validated proposal only: {args.output_dir}/split.patch")
        print("Review before explicit application; no split was changed and no evaluation ran.")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"[error] {exc}\n")


if __name__ == "__main__":
    main()
