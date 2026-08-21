from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

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
