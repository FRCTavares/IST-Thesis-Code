#!/usr/bin/env python3
"""Verify detached historical #58 reproduction against retained cells."""

import argparse
import hashlib
import json
from pathlib import Path


SEQUENCES = (
    "heldout_h01_exit_reentry",
    "heldout_h02_crossing",
    "heldout_h03_occlusion_distractor",
)
FINGERPRINT_ARCHITECTURES = (
    "bytetrack_raw",
    "bytetrack_tim_mars",
    "deepsort_raw",
)
COMMIT = "dc4c5c39cfbe9911b63cb9757d01ca3de096f696"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", required=True, type=Path)
    parser.add_argument("--h01-reproduction", required=True, type=Path)
    parser.add_argument("--h02-h03-reproduction", required=True, type=Path)
    parser.add_argument("--semantic-check-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    details = []
    for sequence in SEQUENCES:
        reproduced = (
            args.h01_reproduction if sequence == SEQUENCES[0]
            else args.h02_h03_reproduction
        )
        provenance = load(reproduced / "run_provenance.json")
        assert provenance["repo_commit"] == COMMIT
        assert provenance["repo_dirty"] is False
        old_path = args.historical / "sequences" / sequence / "cells.json"
        new_path = reproduced / "sequences" / sequence / "cells.json"
        old_cells = {item["architecture_id"]: item for item in load(old_path)}
        new_cells = {item["architecture_id"]: item for item in load(new_path)}
        assert old_cells.keys() == new_cells.keys()
        for architecture, old in old_cells.items():
            new = new_cells[architecture]
            assert old["status"] == new["status"] == "ok"
            assert old["bootstrap"] == new["bootstrap"]
            assert old["evaluation"] == new["evaluation"]
            fingerprint = None
            if architecture in FINGERPRINT_ARCHITECTURES:
                fingerprint = old["generated_semantic_sha256"]
                assert isinstance(fingerprint, str) and len(fingerprint) == 64
                assert fingerprint == new["generated_semantic_sha256"]
            semantic_check = None
            target_metadata_equal = None
            if architecture == "target_reid_090":
                old_meta_path = (
                    args.historical / "sequences" / sequence / "generated_bags"
                    / "target_reid_090.p058_target_reid.json"
                )
                new_meta_path = (
                    reproduced / "sequences" / sequence / "generated_bags"
                    / "target_reid_090.p058_target_reid.json"
                )
                old_meta = load(old_meta_path)
                new_meta = load(new_meta_path)
                for metadata in (old_meta, new_meta):
                    for key in ("input_bag", "output_bag", "model"):
                        metadata.pop(key, None)
                target_metadata_equal = old_meta == new_meta
                assert target_metadata_equal
                semantic_path = args.semantic_check_dir / (
                    sequence + "_target_reid_repeat.json"
                )
                semantic_check = load(semantic_path)
                assert semantic_check["record_times_and_all_deserialised_fields_equal"]
                assert semantic_check["count_a"] == semantic_check["count_b"]
                assert semantic_check["count_a"] == old_meta["target_messages"]
            details.append({
                "sequence_id": sequence,
                "architecture_id": architecture,
                "status_match": True,
                "bootstrap_match": True,
                "frozen_v2_evaluation_match": True,
                "historical_semantic_fingerprint_match": fingerprint is not None,
                "semantic_fingerprint": fingerprint,
                "target_reid_retained_metadata_match": target_metadata_equal,
                "target_reid_repeat_semantic_check": semantic_check,
                "historical_raw_payload_hashes": old["payload_hashes"],
                "reproduced_raw_payload_hashes": new["payload_hashes"],
            })
    payload = {
        "schema_version": 1,
        "authority_commit": COMMIT,
        "historical_result_root": str(args.historical),
        "h01_reproduction_root": str(args.h01_reproduction),
        "h02_h03_reproduction_root": str(args.h02_h03_reproduction),
        "historical_cells_sha256": {
            seq: digest(args.historical / "sequences" / seq / "cells.json")
            for seq in SEQUENCES
        },
        "cells_verified": len(details),
        "checks": details,
        "note": (
            "Target-ReID original MCAP payloads were pruned. Each detached replay "
            "matches the retained frozen-v2 evaluation and metadata; an independent "
            "repeat matches every record timestamp and deserialised TargetState field. "
            "Raw CDR/MCAP SHA differences are reported but are not a semantic contract."
        ),
    }
    assert len(details) == 12
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cells_verified": len(details), "authority_commit": COMMIT}))


if __name__ == "__main__":
    main()
