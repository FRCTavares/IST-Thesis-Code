"""Issue #50: explicit Pixhawk DataFlash retrieval workflow."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "tools/live/retrieve_pixhawk_dataflash.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "retrieve_pixhawk_dataflash",
        MODULE,
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


rdf = _load()


def _catalogue(path: Path, entries: list[tuple[int, int]]) -> Path:
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "id": log_id,
                "size": size,
                "num_logs": len(entries),
                "last_log_num": max(x[0] for x in entries),
                "time_utc": {
                    "sec": 0,
                    "nanosec": 0,
                    "usable": False,
                    "iso8601": None,
                },
            }
            for log_id, size in entries
        ],
    }
    path.write_text(json.dumps(payload))
    return path


def test_compare_requires_exactly_one_new_log(tmp_path):
    before = _catalogue(
        tmp_path / "before.json",
        [(1, 100), (2, 200)],
    )
    after = _catalogue(
        tmp_path / "after.json",
        [(1, 100), (2, 200), (3, 333)],
    )

    code, result = rdf.compare_catalogues(before, after)

    assert code == 0
    assert result["status"] == "unique_new_log"
    assert result["new_log_ids"] == [3]
    assert result["selected"]["id"] == 3
    assert result["selected"]["size"] == 333


def test_compare_fails_closed_when_no_new_log(tmp_path):
    before = _catalogue(
        tmp_path / "before.json",
        [(1, 100), (2, 200)],
    )
    after = _catalogue(
        tmp_path / "after.json",
        [(1, 100), (2, 200)],
    )

    code, result = rdf.compare_catalogues(before, after)

    assert code == 2
    assert result["status"] == "ambiguous"
    assert result["new_log_ids"] == []
    assert result["selected"] is None


def test_compare_fails_closed_when_multiple_new_logs(tmp_path):
    before = _catalogue(
        tmp_path / "before.json",
        [(1, 100)],
    )
    after = _catalogue(
        tmp_path / "after.json",
        [(1, 100), (2, 200), (3, 300)],
    )

    code, result = rdf.compare_catalogues(before, after)

    assert code == 2
    assert result["status"] == "ambiguous"
    assert result["new_log_ids"] == [2, 3]
    assert result["selected"] is None


def test_removed_old_log_does_not_hide_unique_new_log(tmp_path):
    before = _catalogue(
        tmp_path / "before.json",
        [(1, 100), (2, 200)],
    )
    after = _catalogue(
        tmp_path / "after.json",
        [(2, 200), (3, 300)],
    )

    code, result = rdf.compare_catalogues(before, after)

    assert code == 0
    assert result["removed_log_ids"] == [1]
    assert result["new_log_ids"] == [3]
    assert result["selected"]["id"] == 3


def test_invalid_catalogue_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {"id": 2, "size": 0},
                ],
            }
        )
    )

    good = _catalogue(tmp_path / "good.json", [(1, 100)])

    try:
        rdf.compare_catalogues(good, bad)
    except ValueError as exc:
        assert "invalid DataFlash size" in str(exc)
    else:
        raise AssertionError("invalid catalogue unexpectedly accepted")


def test_missing_ranges():
    mask = bytearray(b"\x01\x01\x00\x00\x01\x00\x01")

    assert rdf._missing_ranges(mask) == [(2, 2), (5, 1)]


def test_compare_cli_refuses_to_overwrite_output(tmp_path):
    before = _catalogue(tmp_path / "before.json", [(1, 100)])
    after = _catalogue(
        tmp_path / "after.json",
        [(1, 100), (2, 200)],
    )
    output = tmp_path / "association.json"
    output.write_text("existing\n")

    result = subprocess.run(
        [
            sys.executable,
            str(MODULE),
            "compare",
            "--before",
            str(before),
            "--after",
            str(after),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "refusing to overwrite" in result.stderr
    assert output.read_text() == "existing\n"


def test_download_cli_requires_explicit_id_size_and_output():
    cases = (
        ["download"],
        ["download", "--log-id", "7"],
        ["download", "--log-id", "7", "--expected-size", "123"],
        ["download", "--expected-size", "123", "--output", "/tmp/x.bin"],
    )

    for args in cases:
        result = subprocess.run(
            [sys.executable, str(MODULE), *args],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2


def test_source_has_no_highest_id_or_timestamp_selection():
    source = MODULE.read_text(encoding="utf-8")

    assert "new_ids[0] if new_ids else" not in source
    assert "max(after_ids)" not in source
    assert "max(before_ids)" not in source
    assert "st_mtime" not in source
    assert "getmtime(" not in source
