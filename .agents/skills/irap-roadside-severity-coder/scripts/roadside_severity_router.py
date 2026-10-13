#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - optional dependency in some environments
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]

NO_OBJECT_CATEGORY = "No object"
NO_OBJECT_DISTANCE = ">=10m"

DISTANCE_ORDER = {
    "0 to <1m": 0,
    "1 to <5m": 1,
    "5 to <10m": 2,
    ">=10m": 3,
}

PROJECTION_KEY_ALLOWLIST = {
    "poses",
    "extrinsics",
    "las",
    "image",
    "image_id",
    "pose_model",
    "invert_extrinsics",
    "flip_pano_u",
    "v_top",
    "v_bottom",
    "visualize",
    "visualization_out",
    "max_distance_m",
    "min_intensity",
    "out_las",
}

SEMANTIC_HINT_DEFAULTS: dict[str, dict[str, str]] = {
    "Cliff": {"description": "cliff edge", "dino_label": "cliff"},
    "Tree >=10cm": {"description": "tree trunk", "dino_label": "tree"},
    "Rigid sign, post or pole >=10cm": {"description": "sign pole", "dino_label": "pole"},
    "Unprotected safety barrier end": {"description": "barrier end", "dino_label": "guardrail"},
    "Aggressive vertical face": {"description": "rock face", "dino_label": "wall"},
    "Upwards slope - roll over": {"description": "upward slope", "dino_label": "slope"},
    "Deep drainage ditch": {"description": "deep ditch", "dino_label": "ditch"},
    "Downwards slope": {"description": "downward slope", "dino_label": "slope"},
    "Low rigid object >=20cm high": {"description": "low rigid object", "dino_label": "wall"},
    "Rigid structure or building": {"description": "rigid structure", "dino_label": "building"},
    "Upwards slope - no roll over": {"description": "cut slope", "dino_label": "slope"},
    "Semi-rigid structure or building": {"description": "semi rigid structure", "dino_label": "building"},
    "Safety barrier - concrete": {"description": "concrete barrier", "dino_label": "barrier"},
    "Safety barrier - metal": {"description": "metal guardrail", "dino_label": "guardrail"},
    "Safety barrier - wire rope": {"description": "wire rope barrier", "dino_label": "barrier"},
    "Safety barrier - motorcycle friendly": {"description": "motorcycle barrier", "dino_label": "guardrail"},
}

SIMPLE_LABEL_TOKEN = re.compile(r"^[a-z0-9]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Orchestrate iRAP roadside coding using GroundingDINO detections, "
            "2D-3D projection, and pointcloud distance routing."
        )
    )
    parser.add_argument("--input-json", required=True, help="Input request JSON")
    parser.add_argument("--out-json", required=True, help="Output JSON with coded results")
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Python executable used when calling chained scripts",
    )
    return parser.parse_args()


def normalize_label(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("\u2265", ">=")
    text = " ".join(text.split())
    return text


def canonicalize_distance(value: Any) -> str:
    text = normalize_label(value).lower()
    aliases = {
        "0 to <1m": "0 to <1m",
        "0-<1m": "0 to <1m",
        "1 to <5m": "1 to <5m",
        "1-<5m": "1 to <5m",
        "5 to <10m": "5 to <10m",
        "5-<10m": "5 to <10m",
        ">=10m": ">=10m",
        ">= 10m": ">=10m",
    }
    if text not in aliases:
        raise ValueError(f"Unsupported distance category '{value}'")
    return aliases[text]


def bucket_for_distance(distance_m: float) -> str:
    if distance_m < 1.0:
        return "0 to <1m"
    if distance_m < 5.0:
        return "1 to <5m"
    if distance_m < 10.0:
        return "5 to <10m"
    return ">=10m"


def find_repo_root(anchor: Path) -> Path:
    for candidate in [anchor.resolve(), *anchor.resolve().parents]:
        if (candidate / "scripts" / "bbox_to_points.py").exists() and (
            candidate / ".agents" / "skills"
        ).exists():
            return candidate
    raise FileNotFoundError("Could not find repository root")


def resolve_path(path_value: str, repo_root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_object(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def json_from_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("Script returned empty stdout")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        first = text.find("{")
        last = text.rfind("}")
        if first < 0 or last <= first:
            raise ValueError("Script stdout did not contain JSON")
        parsed = json.loads(text[first : last + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Parsed JSON must be an object")
    return parsed


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode != 0:
        error_text = proc.stderr.strip() or proc.stdout.strip() or "Unknown error"
        raise RuntimeError(error_text)
    return proc


def load_category_ids(path: Path) -> tuple[str, str, dict[str, int], dict[str, int], dict[str, str]]:
    payload = read_json_object(path)
    distance_block = payload.get("distance")
    object_block = payload.get("object")
    if not isinstance(distance_block, dict) or not isinstance(object_block, dict):
        raise ValueError("cat_ids.json must contain 'distance' and 'object' objects")

    distance_col_id = str(distance_block.get("col_id", "RS_D"))
    object_col_id = str(object_block.get("col_id", "RS_O"))

    distance_map: dict[str, int] = {}
    for item in distance_block.get("categories", []):
        if not isinstance(item, dict):
            continue
        category = canonicalize_distance(item.get("category"))
        distance_map[category] = int(item["cat_id"])

    object_map: dict[str, int] = {}
    canonical_by_normalized: dict[str, str] = {}
    for item in object_block.get("categories", []):
        if not isinstance(item, dict):
            continue
        raw = normalize_label(item.get("category"))
        canonical = raw
        object_map[canonical] = int(item["cat_id"])
        canonical_by_normalized[raw.lower()] = canonical

    for canonical in list(object_map.keys()):
        key = canonical.lower()
        canonical_by_normalized[key.replace(">=", ">= ")] = canonical
        canonical_by_normalized[key.replace(">= ", ">=")] = canonical

    canonical_by_normalized["no roadside object"] = NO_OBJECT_CATEGORY
    return distance_col_id, object_col_id, distance_map, object_map, canonical_by_normalized


def canonicalize_object(value: Any, alias_map: dict[str, str]) -> str:
    key = normalize_label(value).lower()
    if key in alias_map:
        return alias_map[key]
    raise ValueError(f"Unsupported object category '{value}'")


def load_risk_table(
    path: Path, alias_map: dict[str, str]
) -> tuple[dict[tuple[str, str], int], dict[str, dict[str, int]]]:
    pair_rank: dict[tuple[str, str], int] = {}
    per_object_bucket_rank: dict[str, dict[str, int]] = {}

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rank = int(row["rank"])
            obj = canonicalize_object(row["object_category"], alias_map)
            distance_raw = normalize_label(row["distance_category"]).lower()
            if distance_raw == "any":
                distances = list(DISTANCE_ORDER.keys())
            else:
                distances = [canonicalize_distance(row["distance_category"])]

            for distance in distances:
                key = (distance, obj)
                if key not in pair_rank or rank < pair_rank[key]:
                    pair_rank[key] = rank

                bucket_map = per_object_bucket_rank.setdefault(obj, {})
                if distance not in bucket_map or rank < bucket_map[distance]:
                    bucket_map[distance] = rank

    return pair_rank, per_object_bucket_rank


def lookup_rank(
    distance_category: str,
    object_category: str,
    pair_rank: dict[tuple[str, str], int],
    per_object_bucket_rank: dict[str, dict[str, int]],
) -> tuple[int | None, str]:
    key = (distance_category, object_category)
    if key in pair_rank:
        return pair_rank[key], "exact"

    by_bucket = per_object_bucket_rank.get(object_category)
    if not by_bucket:
        return None, "unmapped_object"

    target_order = DISTANCE_ORDER[distance_category]
    nearest_bucket = min(
        by_bucket.keys(),
        key=lambda bucket: (abs(DISTANCE_ORDER[bucket] - target_order), DISTANCE_ORDER[bucket]),
    )
    return by_bucket[nearest_bucket], f"fallback_nearest_bucket:{nearest_bucket}"


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_defaults(payload: dict[str, Any], key: str, allowlist: set[str] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    block = payload.get(key)
    if isinstance(block, dict):
        out.update(block)
    if allowlist:
        for field in allowlist:
            if field in payload:
                out[field] = payload[field]
    return out


def normalize_simple_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


def is_simple_dino_label(value: Any) -> bool:
    text = normalize_simple_label(value)
    if not text:
        return False
    words = text.split()
    if len(words) < 1 or len(words) > 2:
        return False
    return all(bool(SIMPLE_LABEL_TOKEN.fullmatch(word)) for word in words)


def default_description_for_category(category: str) -> str:
    defaults = SEMANTIC_HINT_DEFAULTS.get(category)
    if defaults:
        return defaults["description"]

    normalized = normalize_label(category).lower()
    words = [word for word in normalized.replace("-", " ").split() if word not in {"or", "no", "over"}]
    words = words[:4]
    if len(words) >= 2:
        return " ".join(words)
    if len(words) == 1:
        return f"{words[0]} object"
    return "roadside object"


def fallback_simple_label_for_category(category: str) -> str:
    defaults = SEMANTIC_HINT_DEFAULTS.get(category)
    if defaults:
        label = normalize_simple_label(defaults["dino_label"])
        if is_simple_dino_label(label):
            return label

    normalized = normalize_label(category).lower()
    words = [word for word in re.findall(r"[a-z0-9]+", normalized) if word not in {"no", "or", "over", "to"}]
    if not words:
        return "object"
    return words[0]


def read_semantic_label_overrides(
    grounding_cfg: dict[str, Any],
    object_aliases: dict[str, str],
    repo_root: Path,
    warnings: list[str],
) -> dict[str, str]:
    overrides: dict[str, str] = {}

    path_value = grounding_cfg.get("semantic_label_overrides_json")
    if isinstance(path_value, str) and path_value.strip():
        override_path = resolve_path(path_value, repo_root)
        payload = read_json(override_path)
        if isinstance(payload, dict) and isinstance(payload.get("labels"), dict):
            payload = payload["labels"]
        if not isinstance(payload, dict):
            warnings.append(
                f"Ignoring semantic_label_overrides_json '{override_path}': expected JSON object mapping categories to labels."
            )
        else:
            for raw_category, raw_label in payload.items():
                try:
                    category = canonicalize_object(raw_category, object_aliases)
                except ValueError:
                    warnings.append(
                        f"Ignoring semantic override for unsupported category '{raw_category}' from {override_path}."
                    )
                    continue
                if category == NO_OBJECT_CATEGORY:
                    continue
                label = normalize_simple_label(raw_label)
                if not is_simple_dino_label(label):
                    warnings.append(
                        f"Ignoring semantic override for '{category}' because label '{raw_label}' is not a simple 1-2 word detector prompt."
                    )
                    continue
                overrides[category] = label

    inline_value = grounding_cfg.get("semantic_label_overrides")
    if isinstance(inline_value, dict):
        for raw_category, raw_label in inline_value.items():
            try:
                category = canonicalize_object(raw_category, object_aliases)
            except ValueError:
                warnings.append(f"Ignoring inline semantic override for unsupported category '{raw_category}'.")
                continue
            if category == NO_OBJECT_CATEGORY:
                continue
            label = normalize_simple_label(raw_label)
            if not is_simple_dino_label(label):
                warnings.append(
                    f"Ignoring inline semantic override for '{category}' because label '{raw_label}' is not a simple 1-2 word detector prompt."
                )
                continue
            overrides[category] = label

    return overrides


def parse_hint_entry(
    raw_entry: Any,
    side: str,
    index: int,
    object_aliases: dict[str, str],
    warnings: list[str],
) -> dict[str, str] | None:
    if not isinstance(raw_entry, dict):
        warnings.append(f"Ignoring hints[{side}][{index}] because it is not an object.")
        return None

    raw_category = raw_entry.get("irap_category", raw_entry.get("category"))
    try:
        category = canonicalize_object(raw_category, object_aliases)
    except ValueError:
        warnings.append(f"Ignoring hints[{side}][{index}] with unsupported category '{raw_category}'.")
        return None
    if category == NO_OBJECT_CATEGORY:
        return None

    description = normalize_label(raw_entry.get("description", raw_entry.get("object_description")))
    dino_label = str(
        raw_entry.get("dino_label", raw_entry.get("label", raw_entry.get("groundingdino_label", "")))
    ).strip()
    return {
        "irap_category": category,
        "description": description,
        "dino_label": dino_label,
    }


def parse_hint_list(
    raw_list: Any,
    side: str,
    object_aliases: dict[str, str],
    warnings: list[str],
) -> list[dict[str, str]]:
    if raw_list is None:
        return []
    if not isinstance(raw_list, list):
        warnings.append(f"Ignoring hints block for side '{side}' because it is not a list.")
        return []

    parsed: list[dict[str, str]] = []
    for idx, item in enumerate(raw_list):
        entry = parse_hint_entry(item, side, idx, object_aliases, warnings)
        if entry is not None:
            parsed.append(entry)
    return parsed


def parse_hints_by_side(
    payload: Any,
    requested_sides: list[str],
    object_aliases: dict[str, str],
    warnings: list[str],
) -> dict[str, list[dict[str, str]]]:
    if isinstance(payload, list):
        parsed = parse_hint_list(payload, "both", object_aliases, warnings)
        return {side: list(parsed) for side in requested_sides}

    if isinstance(payload, dict):
        if "objects" in payload:
            parsed = parse_hint_list(payload.get("objects"), "objects", object_aliases, warnings)
            return {side: list(parsed) for side in requested_sides}

        parsed_by_side: dict[str, list[dict[str, str]]] = {side: [] for side in requested_sides}
        parsed_both = parse_hint_list(payload.get("both"), "both", object_aliases, warnings)
        for side in requested_sides:
            if side in payload:
                parsed_by_side[side] = parse_hint_list(payload.get(side), side, object_aliases, warnings)
            else:
                parsed_by_side[side] = list(parsed_both)
        return parsed_by_side

    warnings.append("Ignoring hints_json content because it is neither a JSON object nor an array.")
    return {side: [] for side in requested_sides}


def build_default_hint_entries(categories: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for category in categories:
        if category == NO_OBJECT_CATEGORY:
            continue
        out.append(
            {
                "irap_category": category,
                "description": default_description_for_category(category),
                "dino_label": fallback_simple_label_for_category(category),
            }
        )
    return out


def prepare_effective_hints(
    grounding_cfg: dict[str, Any],
    object_aliases: dict[str, str],
    categories_in_order: list[str],
    requested_sides: list[str],
    repo_root: Path,
    work_dir: Path,
    warnings: list[str],
) -> dict[str, Any]:
    semantic_label_map: dict[str, str] = {}
    for category in categories_in_order:
        if category == NO_OBJECT_CATEGORY:
            continue
        semantic_label_map[category] = fallback_simple_label_for_category(category)

    semantic_label_map.update(
        read_semantic_label_overrides(
            grounding_cfg=grounding_cfg,
            object_aliases=object_aliases,
            repo_root=repo_root,
            warnings=warnings,
        )
    )

    for category, label in list(semantic_label_map.items()):
        if not is_simple_dino_label(label):
            fallback = fallback_simple_label_for_category(category)
            warnings.append(
                f"Semantic label '{label}' for '{category}' is invalid; using fallback label '{fallback}'."
            )
            semantic_label_map[category] = fallback

    provided_hints_path: Path | None = None
    hints_json_value = grounding_cfg.get("hints_json")
    if isinstance(hints_json_value, str) and hints_json_value.strip():
        provided_hints_path = resolve_path(hints_json_value, repo_root)
        raw_hints_payload = read_json(provided_hints_path)
        by_side = parse_hints_by_side(
            payload=raw_hints_payload,
            requested_sides=requested_sides,
            object_aliases=object_aliases,
            warnings=warnings,
        )
        hints_source = "provided"
    else:
        by_side = {
            side: build_default_hint_entries(categories_in_order)
            for side in requested_sides
        }
        hints_source = "generated"

    autocorrections: list[dict[str, Any]] = []
    effective_hints_by_side: dict[str, list[dict[str, str]]] = {}

    for side in requested_sides:
        entries = list(by_side.get(side, []))
        if not entries:
            entries = build_default_hint_entries(categories_in_order)
            warnings.append(
                f"No valid hints provided for side '{side}'; using generated semantic defaults."
            )

        seen_categories: set[str] = set()
        effective_entries: list[dict[str, str]] = []
        for idx, entry in enumerate(entries):
            category = entry["irap_category"]
            if category in seen_categories:
                autocorrections.append(
                    {
                        "side": side,
                        "index": idx,
                        "irap_category": category,
                        "field": "irap_category",
                        "reason": "duplicate_category_hint_removed",
                        "from": category,
                        "to": None,
                    }
                )
                continue
            seen_categories.add(category)

            description_raw = normalize_label(entry.get("description"))
            words = [part for part in description_raw.split(" ") if part]
            description_effective = description_raw
            fallback_description = default_description_for_category(category)
            if len(words) < 2 or len(words) > 4:
                description_effective = fallback_description
                if description_raw != description_effective:
                    autocorrections.append(
                        {
                            "side": side,
                            "index": idx,
                            "irap_category": category,
                            "field": "description",
                            "reason": "description_out_of_range_2_to_4_words",
                            "from": description_raw or None,
                            "to": description_effective,
                        }
                    )

            requested_label = normalize_simple_label(entry.get("dino_label"))
            semantic_label = semantic_label_map.get(category, fallback_simple_label_for_category(category))
            if not is_simple_dino_label(semantic_label):
                semantic_label = fallback_simple_label_for_category(category)
                warnings.append(
                    f"Invalid semantic label for '{category}' after processing; using fallback '{semantic_label}'."
                )

            if requested_label != semantic_label:
                autocorrections.append(
                    {
                        "side": side,
                        "index": idx,
                        "irap_category": category,
                        "field": "dino_label",
                        "reason": "semantic_prompt_simplified",
                        "from": requested_label or None,
                        "to": semantic_label,
                    }
                )

            effective_entries.append(
                {
                    "irap_category": category,
                    "description": description_effective,
                    "dino_label": semantic_label,
                }
            )

        effective_hints_by_side[side] = effective_entries

    hints_path = work_dir / "hints.generated.json"
    hints_payload: dict[str, Any] = {
        "description": "Effective semantic detector hints used by roadside_severity_router.",
        "metadata": {
            "source": hints_source,
            "provided_hints_json": str(provided_hints_path) if provided_hints_path else None,
            "requested_sides": requested_sides,
        },
    }
    for side in requested_sides:
        hints_payload[side] = effective_hints_by_side[side]
    write_json(hints_path, hints_payload)

    return {
        "hints_source": hints_source,
        "provided_hints_json": str(provided_hints_path) if provided_hints_path else None,
        "hints_json": str(hints_path),
        "effective_hints_by_side": effective_hints_by_side,
        "hints_autocorrections": autocorrections,
    }


def collect_images(payload: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    images_value = payload.get("images")
    if not isinstance(images_value, list) or not images_value:
        raise ValueError("Input must include non-empty 'images' list")

    entries: list[dict[str, Any]] = []
    for idx, raw in enumerate(images_value):
        if isinstance(raw, str):
            image_raw = raw
            image_id = Path(raw).name
            extra: dict[str, Any] = {}
        elif isinstance(raw, dict):
            image_raw = str(raw.get("image") or raw.get("image_path") or "").strip()
            if not image_raw:
                raise ValueError(f"images[{idx}] missing 'image' path")
            image_id = str(raw.get("image_id") or Path(image_raw).name)
            extra = {k: v for k, v in raw.items() if k not in {"image", "image_path", "image_id"}}
        else:
            raise ValueError(f"images[{idx}] must be a string path or object")

        resolved_image = resolve_path(image_raw, repo_root)
        entry = {
            "image": str(resolved_image),
            "image_name": resolved_image.name,
            "image_id": image_id,
            "overrides": extra,
        }
        entries.append(entry)
    return entries


def image_entry_lookup(entries: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_path = {str(Path(item["image"]).resolve()): item for item in entries}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in entries:
        by_name.setdefault(str(item["image_name"]), []).append(item)
    return by_path, by_name


def resolve_image_entry(
    image_path: str,
    image_name: str,
    by_path: dict[str, dict[str, Any]],
    by_name: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    key = str(Path(image_path).resolve())
    if key in by_path:
        return by_path[key]
    candidates = by_name.get(image_name, [])
    if len(candidates) == 1:
        return candidates[0]
    return None


def build_projection_items(
    detections: dict[str, Any],
    image_entries: list[dict[str, Any]],
    object_aliases: dict[str, str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    by_path, by_name = image_entry_lookup(image_entries)
    items: list[dict[str, Any]] = []

    images = detections.get("images")
    if not isinstance(images, list):
        raise ValueError("Detections payload missing 'images' list")

    for image_data in images:
        if not isinstance(image_data, dict):
            continue
        image_path = str(image_data.get("image_path") or "")
        image_name = str(image_data.get("image_name") or Path(image_path).name)
        entry = resolve_image_entry(image_path=image_path, image_name=image_name, by_path=by_path, by_name=by_name)
        if entry is None:
            warnings.append(
                f"Could not resolve image configuration for detection image '{image_name}'. "
                "Using defaults only."
            )
            entry = {"image": image_path, "image_name": image_name, "image_id": image_name, "overrides": {}}

        side_list = image_data.get("sides")
        if not isinstance(side_list, list):
            continue

        for side_data in side_list:
            if not isinstance(side_data, dict):
                continue
            side = str(side_data.get("side") or "")
            objects = side_data.get("objects")
            if not isinstance(objects, list):
                continue

            for obj_index, obj in enumerate(objects):
                if not isinstance(obj, dict):
                    continue
                raw_category = obj.get("irap_category")
                try:
                    category = canonicalize_object(raw_category, object_aliases)
                except ValueError:
                    warnings.append(f"Skipping object with unsupported category '{raw_category}'")
                    continue
                if category == NO_OBJECT_CATEGORY:
                    continue

                bbox = obj.get("bbox_xyxy")
                if not isinstance(bbox, list) or len(bbox) != 4:
                    warnings.append(
                        f"Skipping object '{category}' on side '{side}' because bbox_xyxy is missing."
                    )
                    continue

                per_image_overrides = {
                    k: v for k, v in dict(entry.get("overrides", {})).items() if k in PROJECTION_KEY_ALLOWLIST
                }

                item: dict[str, Any] = {}
                item.update(per_image_overrides)
                item["bbox"] = bbox
                item["image"] = str(entry["image"])
                item["image_id"] = str(entry["image_id"])
                item["trace_id"] = f"{image_name}:{side}:{obj_index}"
                item["image_name"] = image_name
                item["side"] = side
                item["irap_category"] = category
                item["object_description"] = obj.get("object_description")
                item["confidence"] = obj.get("confidence")
                item["bbox_xyxy"] = bbox
                items.append(item)

    return items


def write_indices_file(path: Path, indices: list[Any]) -> None:
    lines = [str(int(v)) for v in indices]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_distance_objects(
    projection_out: dict[str, Any],
    work_dir: Path,
    warnings: list[str],
) -> list[dict[str, Any]]:
    results = projection_out.get("results")
    if not isinstance(results, list):
        raise ValueError("Projection output missing 'results' list")

    objects: list[dict[str, Any]] = []
    indices_dir = work_dir / "indices"
    indices_dir.mkdir(parents=True, exist_ok=True)

    for idx, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        trace_input = dict(result.get("trace", {}).get("input", {}))
        if result.get("error"):
            warnings.append(f"Projection failed for item {idx}: {result['error']}")
            continue

        indices = result.get("indices")
        if not isinstance(indices, list) or len(indices) == 0:
            trace_id = trace_input.get("trace_id", f"item-{idx}")
            warnings.append(f"Projection returned 0 indices for {trace_id}; skipping distance step.")
            continue

        idx_path = indices_dir / f"object_{idx:05d}.txt"
        write_indices_file(idx_path, indices)

        object_item = {
            "indices_file": str(idx_path),
            "trace_id": trace_input.get("trace_id"),
            "image_path": trace_input.get("image"),
            "image_name": trace_input.get("image_name"),
            "side": trace_input.get("side"),
            "irap_category": trace_input.get("irap_category"),
            "object_description": trace_input.get("object_description"),
            "confidence": trace_input.get("confidence"),
            "bbox_xyxy": trace_input.get("bbox_xyxy"),
            "object_point_count": int(len(indices)),
        }
        objects.append(object_item)

    return objects


def collect_candidate_records(
    distance_out: dict[str, Any],
    pair_rank: dict[tuple[str, str], int],
    per_object_bucket_rank: dict[str, dict[str, int]],
    object_aliases: dict[str, str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    results = distance_out.get("results")
    if not isinstance(results, list):
        raise ValueError("Distance output missing 'results' list")

    candidates: list[dict[str, Any]] = []
    for idx, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        if result.get("error"):
            warnings.append(f"Distance failed for item {idx}: {result['error']}")
            continue

        trace_input = dict(result.get("trace", {}).get("input", {}))
        try:
            object_category = canonicalize_object(trace_input.get("irap_category"), object_aliases)
        except ValueError:
            warnings.append(
                f"Distance result {idx} has unsupported object category '{trace_input.get('irap_category')}'"
            )
            continue

        distance_m = as_float(result.get("min_distance_m"))
        if distance_m is None:
            warnings.append(f"Distance result {idx} missing numeric min_distance_m")
            continue

        distance_category = bucket_for_distance(distance_m)
        risk_rank, rank_source = lookup_rank(
            distance_category=distance_category,
            object_category=object_category,
            pair_rank=pair_rank,
            per_object_bucket_rank=per_object_bucket_rank,
        )
        if risk_rank is None:
            warnings.append(
                f"No risk-rank mapping for pair ({distance_category}, {object_category}); skipping item."
            )
            continue

        candidate = {
            "trace_id": trace_input.get("trace_id"),
            "image_path": trace_input.get("image_path"),
            "image_name": trace_input.get("image_name"),
            "side": trace_input.get("side"),
            "object_category": object_category,
            "distance_category": distance_category,
            "distance_m": distance_m,
            "risk_rank": int(risk_rank),
            "rank_source": rank_source,
            "confidence": as_float(trace_input.get("confidence")),
            "bbox_xyxy": trace_input.get("bbox_xyxy"),
            "object_point_count": trace_input.get("object_point_count"),
        }
        candidates.append(candidate)

    return candidates


def as_bbox_xyxy(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [int(value[0]), int(value[1]), int(value[2]), int(value[3])]
    except (TypeError, ValueError):
        return None


def render_bbox_visualizations(
    detections: dict[str, Any],
    out_dir: Path,
    warnings: list[str],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    if Image is None or ImageDraw is None:
        warnings.append("PIL is not available; skipping bbox visualization rendering.")
        return outputs

    images = detections.get("images")
    if not isinstance(images, list):
        return outputs

    out_dir.mkdir(parents=True, exist_ok=True)
    side_colors = {
        "driver": (220, 20, 60),
        "passenger": (65, 105, 225),
    }

    for image_data in images:
        if not isinstance(image_data, dict):
            continue
        image_path = str(image_data.get("image_path") or "")
        image_name = str(image_data.get("image_name") or Path(image_path).name)
        if not image_path:
            warnings.append(f"Cannot render bbox visualization for '{image_name}': missing image_path.")
            continue

        try:
            canvas = Image.open(image_path).convert("RGB")
        except Exception as exc:
            warnings.append(f"Cannot render bbox visualization for '{image_name}': {exc}")
            continue

        draw = ImageDraw.Draw(canvas)
        box_count = 0

        side_list = image_data.get("sides")
        if isinstance(side_list, list):
            for side_data in side_list:
                if not isinstance(side_data, dict):
                    continue
                side = str(side_data.get("side") or "")
                color = side_colors.get(side, (255, 140, 0))
                objects = side_data.get("objects")
                if not isinstance(objects, list):
                    continue
                for obj in objects:
                    if not isinstance(obj, dict):
                        continue
                    bbox = as_bbox_xyxy(obj.get("bbox_xyxy"))
                    if bbox is None:
                        continue
                    category = normalize_label(obj.get("irap_category"))
                    confidence = as_float(obj.get("confidence"))
                    conf_text = "" if confidence is None else f" {confidence:.2f}"
                    label = f"{side}: {category}{conf_text}".strip()
                    draw.rectangle(bbox, outline=color, width=3)
                    label_anchor = (bbox[0] + 3, max(0, bbox[1] - 14))
                    draw.text(label_anchor, label, fill=color)
                    box_count += 1

        out_path = out_dir / f"{Path(image_name).stem}.bbox_viz.png"
        canvas.save(out_path)
        outputs.append(
            {
                "image_name": image_name,
                "image_path": image_path,
                "visualization_path": str(out_path),
                "box_count": int(box_count),
            }
        )

    return outputs


def build_explainability_payload(
    detections: dict[str, Any],
    projection_out: dict[str, Any],
    distance_out: dict[str, Any],
    image_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    detection_map: dict[tuple[str, str], list[str]] = {}
    detection_box_counts: dict[tuple[str, str], int] = {}

    images = detections.get("images")
    if isinstance(images, list):
        for image_data in images:
            if not isinstance(image_data, dict):
                continue
            image_path = str(image_data.get("image_path") or "")
            side_list = image_data.get("sides")
            if not isinstance(side_list, list):
                continue
            for side_data in side_list:
                if not isinstance(side_data, dict):
                    continue
                side = str(side_data.get("side") or "")
                key = (image_path, side)
                seen_categories: list[str] = []
                count = 0
                objects = side_data.get("objects")
                if not isinstance(objects, list):
                    continue
                for obj in objects:
                    if not isinstance(obj, dict):
                        continue
                    bbox = as_bbox_xyxy(obj.get("bbox_xyxy"))
                    if bbox is None:
                        continue
                    category = normalize_label(obj.get("irap_category"))
                    if category not in seen_categories:
                        seen_categories.append(category)
                    count += 1
                detection_map[key] = seen_categories
                detection_box_counts[key] = count

    projection_success_by_side: dict[tuple[str, str], int] = {}
    projection_results = projection_out.get("results")
    if isinstance(projection_results, list):
        for result in projection_results:
            if not isinstance(result, dict):
                continue
            if result.get("error"):
                continue
            indices = result.get("indices")
            if not isinstance(indices, list) or not indices:
                continue
            trace_input = dict(result.get("trace", {}).get("input", {}))
            key = (str(trace_input.get("image") or ""), str(trace_input.get("side") or ""))
            projection_success_by_side[key] = int(projection_success_by_side.get(key, 0) + 1)

    distance_success_by_side: dict[tuple[str, str], int] = {}
    distance_results = distance_out.get("results")
    if isinstance(distance_results, list):
        for result in distance_results:
            if not isinstance(result, dict):
                continue
            if result.get("error"):
                continue
            if as_float(result.get("min_distance_m")) is None:
                continue
            trace_input = dict(result.get("trace", {}).get("input", {}))
            key = (str(trace_input.get("image_path") or ""), str(trace_input.get("side") or ""))
            distance_success_by_side[key] = int(distance_success_by_side.get(key, 0) + 1)

    explain_images: list[dict[str, Any]] = []
    for image_data in image_outputs:
        image_path = str(image_data.get("image_path") or "")
        image_name = str(image_data.get("image_name") or Path(image_path).name)
        side_messages: list[str] = []
        side_steps: list[dict[str, Any]] = []
        sides = image_data.get("sides")
        if not isinstance(sides, list):
            continue
        for side_result in sides:
            if not isinstance(side_result, dict):
                continue
            side = str(side_result.get("side") or "")
            key = (image_path, side)
            detected_categories = detection_map.get(key, [])
            detected_count = int(detection_box_counts.get(key, 0))
            projected_count = int(projection_success_by_side.get(key, 0))
            distance_count = int(distance_success_by_side.get(key, 0))
            rs_d = side_result.get("rs_d", {})
            rs_o = side_result.get("rs_o", {})
            object_category = rs_o.get("category", "No object")
            distance_category = rs_d.get("category", ">=10m")
            distance_m = side_result.get("distance_m")
            distance_text = "N/A" if distance_m is None else f"{float(distance_m):.2f}m"

            if detected_categories:
                detected_text = ", ".join(detected_categories[:4])
            else:
                detected_text = "no codifiable roadside objects"

            side_summary = (
                f"{side}: detected {detected_count} bbox(es) ({detected_text}); "
                f"projected {projected_count}; measured {distance_count}; "
                f"selected {object_category} at {distance_text} ({distance_category})."
            )
            side_messages.append(side_summary)
            side_steps.append(
                {
                    "side": side,
                    "detection": f"Analyzed {side} side and found {detected_count} candidate bbox(es): {detected_text}.",
                    "projection": (
                        f"Projected {projected_count} candidate object set(s) from 2D bbox to 3D points."
                    ),
                    "distance": (
                        f"Computed {distance_count} distance value(s) against segmented road reference."
                    ),
                    "selection": (
                        f"Highest-severity code is {object_category} at {distance_text} "
                        f"({distance_category}; RS_O={rs_o.get('cat_id')}, RS_D={rs_d.get('cat_id')})."
                    ),
                }
            )

        explain_images.append(
            {
                "image_name": image_name,
                "image_path": image_path,
                "summary": " ".join(side_messages).strip(),
                "steps": side_steps,
            }
        )

    global_summary = (
        f"Processed {len(explain_images)} image(s). "
        "Pipeline: scene analysis + GroundingDINO bbox detection -> bbox-to-point projection -> "
        "road segmentation and object-to-road distance -> iRAP RS_O/RS_D coding."
    )
    return {
        "global_summary": global_summary,
        "images": explain_images,
    }


def init_side_groups(
    detections: dict[str, Any],
    requested_sides: list[str],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[tuple[str, str]]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    ordered_keys: list[tuple[str, str]] = []

    images = detections.get("images")
    if not isinstance(images, list):
        raise ValueError("Detections payload missing 'images' list")

    for image_data in images:
        if not isinstance(image_data, dict):
            continue
        image_path = str(image_data.get("image_path") or "")
        image_name = str(image_data.get("image_name") or Path(image_path).name)
        for side in requested_sides:
            key = (image_path, side)
            if key in groups:
                continue
            groups[key] = {
                "image_path": image_path,
                "image_name": image_name,
                "side": side,
                "candidates": [],
            }
            ordered_keys.append(key)

    return groups, ordered_keys


def candidate_sort_key(item: dict[str, Any]) -> tuple[float, float, float]:
    rank = float(item.get("risk_rank", 9_999_999))
    distance_m = float(item.get("distance_m", 9_999_999.0))
    confidence = as_float(item.get("confidence"))
    confidence_key = -(confidence if confidence is not None else -1.0)
    return (rank, distance_m, confidence_key)


def no_object_selection(pair_rank: dict[tuple[str, str], int]) -> dict[str, Any]:
    return {
        "object_category": NO_OBJECT_CATEGORY,
        "distance_category": NO_OBJECT_DISTANCE,
        "distance_m": None,
        "risk_rank": int(pair_rank.get((NO_OBJECT_DISTANCE, NO_OBJECT_CATEGORY), 56)),
        "rank_source": "default_no_object",
        "trace_id": None,
        "confidence": None,
        "bbox_xyxy": None,
        "object_point_count": 0,
    }


def main() -> int:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__))
    skill_root = Path(__file__).resolve().parents[1]
    references_dir = skill_root / "references"

    input_path = resolve_path(args.input_json, repo_root)
    out_path = resolve_path(args.out_json, repo_root)
    request = read_json_object(input_path)

    distance_col_id, object_col_id, distance_ids, object_ids, object_aliases = load_category_ids(
        references_dir / "cat_ids.json"
    )
    pair_rank, per_object_bucket_rank = load_risk_table(references_dir / "risk_hierarchy.csv", object_aliases)

    side = str(request.get("side", "both")).strip().lower()
    if side not in {"driver", "passenger", "both"}:
        raise ValueError("side must be one of: driver, passenger, both")
    requested_sides = ["driver", "passenger"] if side == "both" else [side]
    categories_in_order = list(object_ids.keys())

    image_entries = collect_images(request, repo_root)
    projection_defaults = collect_defaults(request, "projection_defaults", PROJECTION_KEY_ALLOWLIST)
    distance_defaults = collect_defaults(request, "distance_defaults")
    grounding_cfg = collect_defaults(request, "groundingdino")

    if "las" not in distance_defaults and "las" in projection_defaults:
        distance_defaults["las"] = projection_defaults["las"]

    work_dir_value = request.get("work_dir")
    if isinstance(work_dir_value, str) and work_dir_value.strip():
        work_dir = resolve_path(work_dir_value, repo_root)
    else:
        work_dir = out_path.parent / f"{out_path.stem}_intermediate"
    work_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    hints_source = "not_used"
    hints_autocorrections: list[dict[str, Any]] = []
    effective_hints_by_side: dict[str, list[dict[str, str]]] = {}
    effective_hints_json_path: str | None = None
    provided_hints_json_path: str | None = None

    # Step 1: object detections.
    detections_json_value = request.get("detections_json")
    if isinstance(detections_json_value, str) and detections_json_value.strip():
        detections_path = resolve_path(detections_json_value, repo_root)
        detections = read_json_object(detections_path)
        settings = detections.get("settings")
        if isinstance(settings, dict):
            hints_setting = settings.get("hints_json")
            if isinstance(hints_setting, str) and hints_setting.strip():
                effective_hints_json_path = str(resolve_path(hints_setting, repo_root))
            else:
                effective_hints_json_path = None
        hints_source = "reused_detections"
    else:
        dino_script = repo_root / ".agents" / "skills" / "irap-roadside-groundingdino" / "scripts" / "irap_groundingdino_bbox.py"
        if not dino_script.exists():
            raise FileNotFoundError(f"Missing dependency script: {dino_script}")

        hint_plan = prepare_effective_hints(
            grounding_cfg=grounding_cfg,
            object_aliases=object_aliases,
            categories_in_order=categories_in_order,
            requested_sides=requested_sides,
            repo_root=repo_root,
            work_dir=work_dir,
            warnings=warnings,
        )
        hints_source = str(hint_plan["hints_source"])
        hints_autocorrections = list(hint_plan["hints_autocorrections"])
        effective_hints_by_side = dict(hint_plan["effective_hints_by_side"])
        effective_hints_json_path = str(hint_plan["hints_json"])
        provided_hints_json_path = hint_plan["provided_hints_json"]

        detections_path = work_dir / "detections.json"
        command = [
            args.python_bin,
            str(dino_script),
            "--images",
            *[str(entry["image"]) for entry in image_entries],
            "--side",
            side,
            "--out-json",
            str(detections_path),
            "--hints-json",
            str(effective_hints_json_path),
        ]
        if bool(grounding_cfg.get("merge_default_hints")):
            warnings.append(
                "groundingdino.merge_default_hints=true was ignored because the orchestrator provides a complete effective hints file."
            )
        if "repo_root" in grounding_cfg:
            command.extend(["--repo-root", str(resolve_path(str(grounding_cfg["repo_root"]), repo_root))])
        if "config_file" in grounding_cfg:
            command.extend(["--config-file", str(resolve_path(str(grounding_cfg["config_file"]), repo_root))])
        if "checkpoint_path" in grounding_cfg:
            command.extend(["--checkpoint-path", str(resolve_path(str(grounding_cfg["checkpoint_path"]), repo_root))])
        if "device" in grounding_cfg:
            command.extend(["--device", str(grounding_cfg["device"])])
        if "box_threshold" in grounding_cfg:
            command.extend(["--box-threshold", str(grounding_cfg["box_threshold"])])
        if "text_threshold" in grounding_cfg:
            command.extend(["--text-threshold", str(grounding_cfg["text_threshold"])])
        if "max_detections_per_hint" in grounding_cfg:
            command.extend(["--max-detections-per-hint", str(grounding_cfg["max_detections_per_hint"])])
        if "dedup_iou" in grounding_cfg:
            command.extend(["--dedup-iou", str(grounding_cfg["dedup_iou"])])

        run_command(command)
        detections = read_json_object(detections_path)

        # Keep trace fields aligned with effective hints actually used by the detector.
        settings = detections.get("settings")
        if isinstance(settings, dict):
            hints_setting = settings.get("hints_json")
            if isinstance(hints_setting, str) and hints_setting.strip():
                effective_hints_json_path = str(resolve_path(hints_setting, repo_root))

    bbox_visualizations = render_bbox_visualizations(
        detections=detections,
        out_dir=work_dir / "bbox_visualizations",
        warnings=warnings,
    )

    # Step 2: bbox -> points.
    projection_json_value = request.get("projection_json")
    if isinstance(projection_json_value, str) and projection_json_value.strip():
        projection_out_path = resolve_path(projection_json_value, repo_root)
        projection_out = read_json_object(projection_out_path)
        projection_items = []
    else:
        projection_router = (
            repo_root / ".agents" / "skills" / "projection-dataflow-router" / "scripts" / "projection_router.py"
        )
        if not projection_router.exists():
            raise FileNotFoundError(f"Missing dependency script: {projection_router}")

        projection_items = build_projection_items(
            detections=detections,
            image_entries=image_entries,
            object_aliases=object_aliases,
            warnings=warnings,
        )
        projection_in = {
            "mode": "bbox_to_points",
            "defaults": projection_defaults,
            "items": projection_items,
        }
        projection_in_path = work_dir / "projection_input.json"
        projection_out_path = work_dir / "projection_output.json"
        write_json(projection_in_path, projection_in)

        command = [
            args.python_bin,
            str(projection_router),
            "--input-json",
            str(projection_in_path),
            "--out-json",
            str(projection_out_path),
            "--python-bin",
            args.python_bin,
        ]
        run_command(command)
        projection_out = read_json_object(projection_out_path)

    # Step 3: pointcloud distance to road.
    distance_json_value = request.get("distance_json")
    if isinstance(distance_json_value, str) and distance_json_value.strip():
        distance_out_path = resolve_path(distance_json_value, repo_root)
        distance_out = read_json_object(distance_out_path)
        distance_objects = []
    else:
        pointcloud_router = (
            repo_root
            / ".agents"
            / "skills"
            / "pointcloud-multistep-processor"
            / "scripts"
            / "pointcloud_workflow_router.py"
        )
        if not pointcloud_router.exists():
            raise FileNotFoundError(f"Missing dependency script: {pointcloud_router}")

        distance_objects = build_distance_objects(
            projection_out=projection_out,
            work_dir=work_dir,
            warnings=warnings,
        )
        distance_in: dict[str, Any] = {"mode": "roadside_distance_to_road", **distance_defaults}
        if "outdir" not in distance_in:
            distance_in["outdir"] = str(work_dir / "pointcloud_workflows")
        distance_in["objects"] = distance_objects

        distance_in_path = work_dir / "distance_input.json"
        distance_out_path = work_dir / "distance_output.json"
        write_json(distance_in_path, distance_in)

        command = [
            args.python_bin,
            str(pointcloud_router),
            "--input-json",
            str(distance_in_path),
            "--out-json",
            str(distance_out_path),
            "--python-bin",
            args.python_bin,
        ]
        run_command(command)
        distance_out = read_json_object(distance_out_path)

    candidates = collect_candidate_records(
        distance_out=distance_out,
        pair_rank=pair_rank,
        per_object_bucket_rank=per_object_bucket_rank,
        object_aliases=object_aliases,
        warnings=warnings,
    )

    side_groups, ordered_keys = init_side_groups(detections=detections, requested_sides=requested_sides)
    for candidate in candidates:
        key = (str(candidate.get("image_path") or ""), str(candidate.get("side") or ""))
        if key not in side_groups:
            side_groups[key] = {
                "image_path": key[0],
                "image_name": str(candidate.get("image_name") or Path(key[0]).name),
                "side": key[1],
                "candidates": [],
            }
            ordered_keys.append(key)
            warnings.append(
                f"Candidate {candidate.get('trace_id')} maps to side group not present in detections; created fallback group."
            )
        side_groups[key]["candidates"].append(candidate)

    image_outputs: list[dict[str, Any]] = []
    image_index: dict[str, dict[str, Any]] = {}
    default_no_object = no_object_selection(pair_rank)

    for key in ordered_keys:
        group = side_groups[key]
        image_path = group["image_path"]
        image_name = group["image_name"]
        side_name = group["side"]
        candidates_for_side = list(group.get("candidates", []))

        if candidates_for_side:
            selected = sorted(candidates_for_side, key=candidate_sort_key)[0]
            selection_reason = "lowest_risk_rank"
        else:
            selected = dict(default_no_object)
            selection_reason = "no_valid_candidates"

        distance_category = str(selected["distance_category"])
        object_category = str(selected["object_category"])
        if distance_category not in distance_ids:
            raise ValueError(f"Missing distance Cat ID mapping for '{distance_category}'")
        if object_category not in object_ids:
            raise ValueError(f"Missing object Cat ID mapping for '{object_category}'")

        side_result = {
            "side": side_name,
            "rs_d": {
                "col_id": distance_col_id,
                "cat_id": int(distance_ids[distance_category]),
                "category": distance_category,
            },
            "rs_o": {
                "col_id": object_col_id,
                "cat_id": int(object_ids[object_category]),
                "category": object_category,
            },
            "risk_rank": int(selected["risk_rank"]),
            "distance_m": selected.get("distance_m"),
            "selection_reason": selection_reason,
            "rank_source": selected.get("rank_source"),
            "selected_trace_id": selected.get("trace_id"),
            "selected_confidence": selected.get("confidence"),
            "selected_bbox_xyxy": selected.get("bbox_xyxy"),
            "selected_object_point_count": selected.get("object_point_count"),
            "candidates_considered": [
                {
                    "trace_id": cand.get("trace_id"),
                    "object_category": cand.get("object_category"),
                    "distance_category": cand.get("distance_category"),
                    "distance_m": cand.get("distance_m"),
                    "risk_rank": cand.get("risk_rank"),
                    "rank_source": cand.get("rank_source"),
                    "confidence": cand.get("confidence"),
                }
                for cand in sorted(candidates_for_side, key=candidate_sort_key)
            ],
        }

        if image_path not in image_index:
            image_entry = {
                "image_path": image_path,
                "image_name": image_name,
                "sides": [],
            }
            image_outputs.append(image_entry)
            image_index[image_path] = image_entry
        image_index[image_path]["sides"].append(side_result)

    explainability = build_explainability_payload(
        detections=detections,
        projection_out=projection_out,
        distance_out=distance_out,
        image_outputs=image_outputs,
    )
    explainability_path = work_dir / "explainability.json"
    write_json(explainability_path, explainability)

    output = {
        "mode": "irap_roadside_severity_coding",
        "requested_side_mode": side,
        "columns": {
            "distance_field_id": distance_col_id,
            "object_field_id": object_col_id,
        },
        "artifacts": {
            "input_json": str(input_path),
            "detections_json": str(detections_path),
            "projection_json": str(projection_out_path),
            "distance_json": str(distance_out_path),
            "hints_json": effective_hints_json_path,
            "hints_input_json": provided_hints_json_path,
            "explainability_json": str(explainability_path),
            "work_dir": str(work_dir),
        },
        "counts": {
            "images": int(len(image_outputs)),
            "requested_side_results": int(sum(len(image_data["sides"]) for image_data in image_outputs)),
            "projection_items": int(len(projection_items)),
            "distance_objects": int(len(distance_objects)),
            "candidates": int(len(candidates)),
            "bbox_visualizations": int(len(bbox_visualizations)),
            "hints_autocorrections": int(len(hints_autocorrections)),
            "warnings": int(len(warnings)),
        },
        "hints_source": hints_source,
        "effective_hints_by_side": effective_hints_by_side,
        "hints_autocorrections": hints_autocorrections,
        "bbox_visualizations": bbox_visualizations,
        "explainability": explainability,
        "images": image_outputs,
        "warnings": warnings,
    }

    write_json(out_path, output)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
