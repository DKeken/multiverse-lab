from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MAX_TRACKED_BYTES = 10 * 1024 * 1024
PRIVATE_MARKERS = (
    re.compile(r"tail[0-9]+" + re.escape(".ts.net")),
    re.compile(r"/" + "Users/[^/]+"),
    re.compile(r"BEGIN " + r"(?:RSA|OPENSSH|EC) PRIVATE KEY"),
)
SCANNER_PATH = Path("scripts/check_artifacts.py")


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [Path(raw.decode()) for raw in result.stdout.split(b"\0") if raw]


for relative_path in tracked_paths():
    path = ROOT / relative_path
    if path.stat().st_size > MAX_TRACKED_BYTES:
        raise ValueError(f"{relative_path}: tracked file exceeds 10 MiB")
    if relative_path == SCANNER_PATH:
        continue
    text = path.read_text(errors="ignore")
    for marker in PRIVATE_MARKERS:
        if marker.search(text):
            raise ValueError(f"{relative_path}: private marker {marker.pattern!r}")


for path in [*ROOT.glob("research/*.json"), *ROOT.glob("results/*.json"), ROOT / "data/registry.json"]:
    value = json.loads(path.read_text())
    if path.name.endswith(".schema.json"):
        Draft202012Validator.check_schema(value)

for path in [
    *ROOT.glob("research/*.yml"),
    *ROOT.glob("research/*.yaml"),
    *ROOT.glob(".github/**/*.yml"),
    *ROOT.glob(".github/**/*.yaml"),
    ROOT / "CITATION.cff",
]:
    yaml.safe_load(path.read_text())

for path in ROOT.glob("research/*.csv"):
    rows = list(csv.reader(path.open(newline="")))
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError(f"{path}: inconsistent CSV widths {sorted(widths)}")

print("research artifacts: valid")
