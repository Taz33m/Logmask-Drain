"""Dataset and ground-truth loading helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
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


@dataclass(frozen=True)
class GroundTruthDataset:
    templates: list[str]
    typed_templates: list[str] | None
    clusters: list[str]
    template_column: str
    typed_template_column: str | None
    cluster_column: str | None
    label_source: str


@dataclass(frozen=True)
class LogHubStructuredDataset:
    logs: list[str]
    templates: list[str]
    typed_templates: list[str] | None
    clusters: list[str]
    content_column: str
    template_column: str
    typed_template_column: str | None
    cluster_column: str | None
    label_source: str


def _first_present(fieldnames: list[str], candidates: list[str]) -> str | None:
    exact = set(fieldnames)
    for candidate in candidates:
        if candidate in exact:
            return candidate
    lowered = {name.lower(): name for name in fieldnames}
    for candidate in candidates:
        found = lowered.get(candidate.lower())
        if found is not None:
            return found
    return None


def _sort_structured_rows(rows: list[dict[str, str]], fieldnames: list[str]) -> list[dict[str, str]]:
    line_id_column = _first_present(fieldnames, ["LineId", "line_id", "lineid"])
    if line_id_column is None:
        return rows
    try:
        return sorted(rows, key=lambda row: int(row[line_id_column]))
    except (TypeError, ValueError):
        return rows


def load_loghub_structured_csv(
    path: str | Path,
    *,
    label_source: str = "structured_csv",
) -> LogHubStructuredDataset:
    """Load a LogHub-style *_structured.csv file with explicit label provenance."""

    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("LogHub structured CSV has no header")
        fieldnames = list(reader.fieldnames)
        content_column = _first_present(fieldnames, ["Content", "content", "Message", "message"])
        template_column = _first_present(
            fieldnames,
            ["EventTemplate", "event_template", "template", "Template"],
        )
        typed_template_column = _first_present(fieldnames, ["TypedEventTemplate", "typed_template"])
        cluster_column = _first_present(fieldnames, ["EventId", "event_id", "eventid", "cluster", "Cluster"])
        if content_column is None:
            raise ValueError("LogHub structured CSV must contain a Content column")
        if template_column is None:
            raise ValueError("LogHub structured CSV must contain an EventTemplate column")

        rows = _sort_structured_rows(list(reader), fieldnames)
        logs = [row[content_column] for row in rows]
        templates = [row[template_column] for row in rows]
        typed_templates = [row[typed_template_column] for row in rows] if typed_template_column is not None else None
        clusters = [row[cluster_column] for row in rows] if cluster_column is not None else templates
        return LogHubStructuredDataset(
            logs=logs,
            templates=templates,
            typed_templates=typed_templates,
            clusters=clusters,
            content_column=content_column,
            template_column=template_column,
            typed_template_column=typed_template_column,
            cluster_column=cluster_column,
            label_source=label_source,
        )


def load_ground_truth_dataset(
    path: str | Path,
    *,
    label_source: str = "ground_truth_csv",
) -> GroundTruthDataset:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("ground-truth CSV has no header")
        fieldnames = list(reader.fieldnames)
        template_column = _first_present(fieldnames, ["template", "event_template", "EventTemplate", "Template"])
        typed_template_column = _first_present(fieldnames, ["typed_template", "TypedEventTemplate"])
        cluster_column = _first_present(fieldnames, ["event_id", "EventId", "eventid", "cluster", "Cluster"])
        if template_column is None:
            raise ValueError("ground-truth CSV must contain a template or event_template column")
        rows = list(reader)
        if _first_present(fieldnames, ["line_id", "LineId", "lineid"]) is not None:
            rows = _sort_structured_rows(rows, fieldnames)
        templates = [row[template_column] for row in rows]
        typed_templates = [row[typed_template_column] for row in rows] if typed_template_column is not None else None
        clusters = [row[cluster_column] for row in rows] if cluster_column is not None else templates
        return GroundTruthDataset(
            templates=templates,
            typed_templates=typed_templates,
            clusters=clusters,
            template_column=template_column,
            typed_template_column=typed_template_column,
            cluster_column=cluster_column,
            label_source=label_source,
        )
