"""JSON and hashing helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel

from .models import MaskBundle, MaskSpec, ParsedLine


def model_to_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=False)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        model_to_data(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def bundle_sha256(bundle: MaskBundle) -> str:
    return sha256_text(canonical_json(bundle))


def runtime_mask_projection(bundle_or_masks: MaskBundle | Iterable[MaskSpec]) -> list[dict[str, Any]]:
    if isinstance(bundle_or_masks, MaskBundle):
        masks = bundle_or_masks.masks
    else:
        masks = list(bundle_or_masks)

    projection: list[dict[str, Any]] = []
    for mask in sorted(
        (m for m in masks if m.enabled),
        key=lambda item: (-item.priority, item.name, item.pattern),
    ):
        projection.append(
            {
                "name": mask.name,
                "type": mask.type,
                "pattern": mask.pattern,
                "flags": sorted(mask.flags),
                "value_group": mask.value_group,
                "replacement": mask.replacement,
                "priority": mask.priority,
                "enabled": mask.enabled,
            }
        )
    return projection


def runtime_mask_sha256(bundle_or_masks: MaskBundle | Iterable[MaskSpec]) -> str:
    return sha256_text(canonical_json(runtime_mask_projection(bundle_or_masks)))


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, value: str) -> None:
    Path(path).write_text(value, encoding="utf-8")


def read_lines(path: str | Path) -> list[str]:
    text = read_text(path)
    return text.splitlines()


def write_lines(path: str | Path, lines: Iterable[str]) -> None:
    write_text(path, "\n".join(lines) + "\n")


def load_json(path: str | Path) -> Any:
    path_object = Path(path)
    text = read_text(path_object)
    if path_object.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - depends on optional extra.
            raise RuntimeError(
                "YAML mask-bundle loading requires the optional dependency: "
                "pip install 'logmask-drain[yaml]'"
            ) from exc
        loaded = yaml.safe_load(text)
        return {} if loaded is None else loaded
    return json.loads(text)


def save_json(path: str | Path, value: Any) -> None:
    data = model_to_data(value)
    rendered = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    write_text(path, rendered + "\n")


def load_mask_bundle(path: str | Path) -> MaskBundle:
    return MaskBundle.model_validate(load_json(path))


def save_mask_bundle(path: str | Path, bundle: MaskBundle) -> None:
    save_json(path, bundle)


def write_jsonl(path: str | Path, rows: Iterable[BaseModel | dict[str, Any]]) -> None:
    rendered = []
    for row in rows:
        data = model_to_data(row)
        rendered.append(json.dumps(data, ensure_ascii=False, sort_keys=True))
    write_text(path, "\n".join(rendered) + ("\n" if rendered else ""))


def load_parsed_jsonl(path: str | Path) -> list[ParsedLine]:
    rows: list[ParsedLine] = []
    for line in read_lines(path):
        if line.strip():
            rows.append(ParsedLine.model_validate_json(line))
    return rows
