"""Dataset and ground-truth loading helpers."""

from __future__ import annotations

import csv
from pathlib import Path


def load_ground_truth_templates(path: str | Path) -> list[str]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("ground-truth CSV has no header")
        fieldnames = set(reader.fieldnames)
        template_field = "template" if "template" in fieldnames else "event_template"
        if template_field not in fieldnames:
            raise ValueError("ground-truth CSV must contain a template or event_template column")
        rows = list(reader)
        if "line_id" in fieldnames:
            rows.sort(key=lambda row: int(row["line_id"]))
        return [row[template_field] for row in rows]

