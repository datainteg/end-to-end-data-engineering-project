"""Manifest integrity checks independent of local disk or S3 transport."""
import hashlib
import json
import re
from datetime import datetime
from .fixture import DATASETS


def stamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("Expected timezone-aware UTC timestamp")
    return dt


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Invalid batch/attempt identifier")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(manifest, metadata):
    """metadata(key) returns bytes and SHA256; raises if the object is absent."""
    if manifest.get("schema_version") != 1 or manifest.get("pipeline_id") != "ecommerce":
        raise ValueError("Unsupported manifest contract")
    b, a = identifier(manifest["batch_id"]), identifier(manifest["attempt_id"])
    upper = stamp(manifest["window_upper_utc"])
    datasets = manifest["datasets"]
    names = [d["name"] for d in datasets]
    if len(names) != len(set(names)) or set(names) != set(DATASETS):
        raise ValueError("Missing, duplicate or unexpected dataset")
    seen = set()
    for d in datasets:
        if d["status"] != "COMPLETE" or d["upper_utc"] != manifest["window_upper_utc"]:
            raise ValueError("Incomplete dataset or inconsistent upper bound")
        if stamp(d["lower_utc"]) > upper:
            raise ValueError("Invalid window")
        if type(d["record_count"]) is not int or d["record_count"] < 0:
            raise ValueError("Invalid record count")
        if d["record_count"] > 0 and not d["files"]:
            raise ValueError("Nonempty dataset without files")
        expected_source = "mongodb" if d["name"] == "customers" else "postgresql"
        if d["source"] != expected_source or d["mode"] not in {"snapshot", "delta", "affected-orders"}:
            raise ValueError("Invalid source or extraction mode")
        if not re.fullmatch(r"[a-f0-9]{64}", d["schema_fingerprint"]):
            raise ValueError("Invalid schema fingerprint")
        prefix = f"raw/batch_id={b}/attempt_id={a}/dataset={d['name']}/"
        for f in d["files"]:
            key = f["key"]
            if not key.startswith(prefix) or ".." in key.split("/") or key in seen:
                raise ValueError("Invalid or duplicate file reference")
            seen.add(key)
            actual = metadata(key)
            if actual["bytes"] != f["bytes"] or actual["sha256"] != f["sha256"]:
                raise ValueError("Object size/checksum mismatch")
    return manifest
