"""Operational Stage-7 ready-input checks; no replay or metric computation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re

import yaml

from physical_target_reference_v2 import load_physical_reference

ACTIVE_SPLIT_ID = "tim_mars_split_v4_2026_09_08"
METADATA_FIELDS = ("people_group", "clothing_group", "overlap_record", "historical_exposure")
SHA256 = re.compile(r"[0-9a-f]{64}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("evidence path must be non-empty")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in value:
        raise ValueError(f"evidence path must be repository-relative: {value}")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"evidence path escapes repository: {value}")
    return path


def source_inventory(root: Path, source_path: str) -> list[dict]:
    source = evidence_path(root, source_path)
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"source bag missing or symlinked: {source_path}")
    if not (source / "metadata.yaml").is_file():
        raise ValueError("source_path must be the finalized bag, not its scenario parent")
    paths = sorted(source.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("source bag must not contain symlinks")
    return [
        {"path": path.relative_to(root).as_posix(),
         "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in paths if path.is_file()
    ]


def verify_source_inventory(root: Path, source_path: str, records: list,
                            *, verify_hashes: bool) -> None:
    source = evidence_path(root, source_path)
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"source bag missing or symlinked: {source_path}")
    if not (source / "metadata.yaml").is_file():
        raise ValueError("source_path must be the finalized bag, not its scenario parent")
    paths = sorted(source.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("source bag must not contain symlinks")
    actual = {path.relative_to(root).as_posix() for path in paths if path.is_file()}
    if not isinstance(records, list) or not records:
        raise ValueError("source files inventory must be non-empty")
    recorded = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("source file record must be an object")
        name = record.get("path")
        path = evidence_path(root, name)
        recorded.append(name)
        if not path.is_file() or type(record.get("size_bytes")) is not int:
            raise ValueError(f"invalid source file/size record: {name}")
        if not SHA256.fullmatch(str(record.get("sha256", ""))):
            raise ValueError(f"invalid source SHA-256: {name}")
        if path.stat().st_size != record["size_bytes"]:
            raise ValueError(f"source size mismatch: {name}")
        if verify_hashes and sha256_file(path) != record["sha256"]:
            raise ValueError(f"source SHA-256 mismatch: {name}")
    if len(recorded) != len(set(recorded)) or set(recorded) != actual:
        raise ValueError("source inventory must cover exactly every file in source_path")
    metadata_path = source / "metadata.yaml"
    if not metadata_path.is_file():
        raise ValueError("source_path must be the finalized bag, not its scenario parent")
    metadata = yaml.safe_load(metadata_path.read_text())["rosbag2_bagfile_information"]
    if metadata.get("storage_identifier") != "mcap":
        raise ValueError("held-out source must use MCAP storage")
    payloads = metadata.get("relative_file_paths", [])
    if not payloads or any(
        not isinstance(name, str) or PurePosixPath(name).name != name
        or not name.endswith(".mcap") for name in payloads
    ):
        raise ValueError("invalid source metadata payload list")
    if len(payloads) != len(set(payloads)):
        raise ValueError("duplicate source payload")
    actual_payloads = {path.name for path in source.glob("*.mcap")}
    if actual_payloads != set(payloads):
        raise ValueError("source metadata and MCAP payloads disagree")
    counts = {
        row["topic_metadata"]["name"]: row["message_count"]
        for row in metadata.get("topics_with_message_count", [])
    }
    if set(counts) != {"/camera/image_raw", "/detections"} or any(
        type(count) is not int or count <= 0 for count in counts.values()
    ):
        raise ValueError("source must retain only non-empty image_raw and detections topics")


def validate_ready_entry(entry: dict, root: Path, *, verify_hashes: bool) -> None:
    if entry.get("status") != "ready":
        raise ValueError("entry must be ready")
    for field in METADATA_FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip() or value.strip() == "pending_capture":
            raise ValueError(f"missing explicit {field}")
    # Retain the legacy integer slot without claiming a pre-release tracker ID.
    if type(entry.get("selected_target_id")) is not int or entry["selected_target_id"] != 0:
        raise ValueError("Stage-7 selected_target_id must be 0 (unresolved; physical-v2 bootstrap only)")
    source = evidence_path(root, entry.get("source_path"))
    annotation = evidence_path(root, entry.get("annotation_path"))
    expected = entry.get("annotation_sha256")
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        raise ValueError("annotation_sha256 must be a frozen SHA-256")
    if not annotation.is_file():
        raise ValueError("annotation_path must be an existing physical-v2 reference")
    if verify_hashes and sha256_file(annotation) != expected:
        raise ValueError("annotation SHA-256 mismatch")
    verify_source_inventory(root, entry["source_path"], entry.get("files"),
                            verify_hashes=verify_hashes)
    reference = load_physical_reference(annotation)
    provenance = reference.provenance
    if provenance.sequence_id != entry["id"]:
        raise ValueError("annotation sequence_id differs from split entry")
    if evidence_path(root, provenance.source_bag_path).resolve() != source.resolve():
        raise ValueError("annotation source_bag_path differs from source_path")
    if provenance.source_bag_name != source.name:
        raise ValueError("annotation source_bag_name differs from source_path")
    if (provenance.source_width, provenance.source_height) != (640, 480):
        raise ValueError("held-out physical reference must use the frozen 640x480 source")
    if provenance.source_image_topic != "/camera/image_raw":
        raise ValueError("annotation source image topic mismatch")
    # Capture provenance is retained and hashed with the source, never guessed.
    runtime = json.loads((source / "run_metadata.json").read_text())
    git = runtime.get("git", {})
    if not re.fullmatch(r"[0-9a-f]{40}", str(git.get("commit", ""))) or git.get("dirty") is not False:
        raise ValueError("capture run_metadata.json must record a clean full Git commit")
