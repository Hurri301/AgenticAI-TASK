#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NO_OBJECT_CATEGORY = "No object"
VALID_SIDES = ("driver", "passenger")


@dataclass(frozen=True)
class ElementRule:
    irap_category: str
    description: str
    dino_label: str
    patterns: tuple[str, ...]


ELEMENT_RULES: list[ElementRule] = [
    ElementRule(
        irap_category="Rigid sign, post or pole >=10cm",
        description="utility pole",
        dino_label="pole",
        patterns=(r"\butility poles?\b", r"\bpoles?\b", r"\bposts?\b"),
    ),
    ElementRule(
        irap_category="Rigid sign, post or pole >=10cm",
        description="road signpost",
        dino_label="signpost",
        patterns=(r"\bsignposts?\b", r"\bsign posts?\b"),
    ),
    ElementRule(
        irap_category="Rigid sign, post or pole >=10cm",
        description="road sign",
        dino_label="sign",
        patterns=(r"\broad signs?\b", r"\btraffic signs?\b", r"\bsigns?\b"),
    ),
    ElementRule(
        irap_category="Tree >=10cm",
        description="mature tree",
        dino_label="tree",
        patterns=(r"\bmature trees?\b", r"\btrees?\b", r"\btrunks?\b"),
    ),
    ElementRule(
        irap_category="Safety barrier - metal",
        description="metal guardrail",
        dino_label="guardrail",
        patterns=(
            r"\bguardrails?\b",
            r"\bmetal barriers?\b",
            r"\bsteel barriers?\b",
            r"\bw[\s\-]?beam\b",
        ),
    ),
    ElementRule(
        irap_category="Safety barrier - concrete",
        description="concrete barrier",
        dino_label="concrete barrier",
        patterns=(
            r"\bconcrete barriers?\b",
            r"\bjersey barriers?\b",
            r"\bconcrete walls?\b",
        ),
    ),
    ElementRule(
        irap_category="Safety barrier - wire rope",
        description="wire rope barrier",
        dino_label="wire barrier",
        patterns=(r"\bwire rope barriers?\b", r"\bcable barriers?\b"),
    ),
    ElementRule(
        irap_category="Safety barrier - motorcycle friendly",
        description="motorcycle barrier",
        dino_label="motorcycle barrier",
        patterns=(
            r"\bmotorcycle barriers?\b",
            r"\bmotorcyclist barriers?\b",
            r"\bmotorcycle friendly barriers?\b",
        ),
    ),
    ElementRule(
        irap_category="Unprotected safety barrier end",
        description="barrier end",
        dino_label="barrier end",
        patterns=(
            r"\bbarrier ends?\b",
            r"\bguardrail ends?\b",
            r"\bunprotected barrier ends?\b",
            r"\bexposed (?:guardrail|barrier) ends?\b",
        ),
    ),
    ElementRule(
        irap_category="Rigid structure or building",
        description="retaining wall",
        dino_label="retaining wall",
        patterns=(
            r"\bretaining walls?\b",
            r"\bbuildings?\b",
            r"\bhouse walls?\b",
            r"\bmasonry walls?\b",
        ),
    ),
    ElementRule(
        irap_category="Semi-rigid structure or building",
        description="brick wall",
        dino_label="brick wall",
        patterns=(
            r"\bbrick walls?\b",
            r"\bfences?\b",
            r"\bwooden fences?\b",
            r"\bboundary walls?\b",
        ),
    ),
    ElementRule(
        irap_category="Low rigid object >=20cm high",
        description="low concrete wall",
        dino_label="low wall",
        patterns=(
            r"\blow walls?\b",
            r"\bcurbs?\b",
            r"\bkerbs?\b",
            r"\bconcrete blocks?\b",
        ),
    ),
    ElementRule(
        irap_category="Aggressive vertical face",
        description="rock face",
        dino_label="rock face",
        patterns=(r"\brock faces?\b", r"\bvertical rock cuts?\b", r"\bvertical faces?\b"),
    ),
    ElementRule(
        irap_category="Cliff",
        description="cliff edge",
        dino_label="cliff",
        patterns=(r"\bcliffs?\b", r"\bcliff edges?\b", r"\bprecipices?\b"),
    ),
    ElementRule(
        irap_category="Deep drainage ditch",
        description="deep ditch",
        dino_label="ditch",
        patterns=(r"\bdeep ditches?\b", r"\bdrainage ditches?\b", r"\broadside trenches?\b"),
    ),
    ElementRule(
        irap_category="Downwards slope",
        description="steep roadside drop",
        dino_label="steep slope",
        patterns=(r"\bdownward slopes?\b", r"\bsteep drops?\b", r"\broadside drops?\b"),
    ),
    ElementRule(
        irap_category="Upwards slope - roll over",
        description="earth embankment",
        dino_label="embankment",
        patterns=(r"\bearth embankments?\b", r"\bfill slopes?\b"),
    ),
    ElementRule(
        irap_category="Upwards slope - no roll over",
        description="steep cut slope",
        dino_label="cut slope",
        patterns=(r"\bcut slopes?\b", r"\bsteep cut slopes?\b"),
    ),
]

NEGATION_PATTERN = re.compile(
    r"\b(no|not|without|none|absent|missing|lack|lacking|lack of)\b",
    re.IGNORECASE,
)
EXPLICIT_NO_OBJECT_PATTERN = re.compile(
    r"\b(no fixed objects?|no roadside objects?|no hazards?|clear roadside|clear zone)\b",
    re.IGNORECASE,
)
PASSENGER_SIDE_PATTERN = re.compile(
    r"\b(passenger side|left side|left roadside|left shoulder)\b",
    re.IGNORECASE,
)
DRIVER_SIDE_PATTERN = re.compile(
    r"\b(driver side|right side|right roadside|right shoulder)\b",
    re.IGNORECASE,
)


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def normalize_text(text: str) -> str:
    normalized = text.lower()
    normalized = normalized.replace("/", " ").replace("-", " ")
    normalized = re.sub(r"[\(\)\[\],;:]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def is_negated(description: str, match_start: int) -> bool:
    prefix = description[max(0, match_start - 48) : match_start]
    return bool(NEGATION_PATTERN.search(prefix))


def infer_side_from_common_description(description: str) -> str:
    passenger_flag = bool(PASSENGER_SIDE_PATTERN.search(description))
    driver_flag = bool(DRIVER_SIDE_PATTERN.search(description))
    if passenger_flag and not driver_flag:
        return "passenger"
    if driver_flag and not passenger_flag:
        return "driver"
    return "both"


def first_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def resolve_side_descriptions(record: dict[str, Any], side_mode: str) -> dict[str, str]:
    common = first_text(record, "description", "image_description", "text")
    driver = first_text(record, "driver_description", "driver")
    passenger = first_text(record, "passenger_description", "passenger")

    if not any([common, driver, passenger]):
        raise ValueError(
            "Each item must include 'description' or side-specific text fields "
            "('driver_description' / 'passenger_description')."
        )

    if side_mode == "driver":
        chosen = driver or common
        return {"driver": chosen}
    if side_mode == "passenger":
        chosen = passenger or common
        return {"passenger": chosen}

    if not driver and not passenger:
        inferred = infer_side_from_common_description(normalize_text(common))
        if inferred == "driver":
            driver = common
        elif inferred == "passenger":
            passenger = common
        else:
            driver = common
            passenger = common
    else:
        if not driver and common:
            driver = common
        if not passenger and common:
            passenger = common

    return {"driver": driver, "passenger": passenger}


def extract_objects_from_description(description: str, max_elements: int) -> list[dict[str, Any]]:
    normalized = normalize_text(description)
    matches: list[tuple[int, int, ElementRule, str]] = []

    for rule_index, rule in enumerate(ELEMENT_RULES):
        for pattern in rule.patterns:
            for match in re.finditer(pattern, normalized):
                if is_negated(normalized, match.start()):
                    continue
                matches.append((match.start(), rule_index, rule, match.group(0)))

    matches.sort(key=lambda item: (item[0], item[1]))

    objects: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _, _, rule, matched_text in matches:
        signature = (rule.irap_category, rule.dino_label)
        if signature in seen:
            continue
        seen.add(signature)
        objects.append(
            {
                "irap_category": rule.irap_category,
                "description": rule.description,
                "dino_label": rule.dino_label,
                "matched_text": matched_text,
            }
        )
        if len(objects) >= max_elements:
            break

    if objects:
        return objects

    if EXPLICIT_NO_OBJECT_PATTERN.search(normalized):
        return [
            {
                "irap_category": NO_OBJECT_CATEGORY,
                "description": "no roadside object",
                "dino_label": "N/A",
                "matched_text": "explicit no-object statement",
            }
        ]

    return [
        {
            "irap_category": NO_OBJECT_CATEGORY,
            "description": "no roadside object",
            "dino_label": "N/A",
            "matched_text": None,
        }
    ]


def build_side_result(side: str, description: str, max_elements: int) -> dict[str, Any]:
    if not isinstance(description, str):
        description = ""
    text = description.strip()
    objects = extract_objects_from_description(text, max_elements=max_elements) if text else [
        {
            "irap_category": NO_OBJECT_CATEGORY,
            "description": "no roadside object",
            "dino_label": "N/A",
            "matched_text": "missing side description",
        }
    ]

    prompt_terms = [item["dino_label"] for item in objects if item["irap_category"] != NO_OBJECT_CATEGORY]
    irap_elements = [item["irap_category"] for item in objects if item["irap_category"] != NO_OBJECT_CATEGORY]
    hint_objects = [
        {
            "irap_category": item["irap_category"],
            "description": item["description"],
            "dino_label": item["dino_label"],
        }
        for item in objects
        if item["irap_category"] != NO_OBJECT_CATEGORY
    ]

    return {
        "side": side,
        "source_description": text,
        "irap_elements": irap_elements if irap_elements else [NO_OBJECT_CATEGORY],
        "groundingdino_prompt": " . ".join(prompt_terms),
        "objects": objects,
        "hints": hint_objects,
    }


def parse_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if "images" in payload:
            images = payload["images"]
            if not isinstance(images, list):
                raise ValueError("'images' must be a JSON array.")
            if not all(isinstance(item, dict) for item in images):
                raise ValueError("Each entry in 'images' must be a JSON object.")
            return images
        return [payload]
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("Each entry in the input array must be a JSON object.")
        return payload
    raise ValueError("Input JSON must be an object or array of objects.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert natural-language roadside descriptions into iRAP categories and "
            "GroundingDINO prompt hints."
        )
    )
    parser.add_argument("--input-json", required=True, help="Input JSON with natural-language descriptions.")
    parser.add_argument("--out-json", required=True, help="Output JSON path.")
    parser.add_argument(
        "--out-hints-json",
        default=None,
        help=(
            "Optional output hints JSON. If one input item is provided, the output is directly "
            "compatible with irap_groundingdino_bbox.py --hints-json."
        ),
    )
    parser.add_argument(
        "--side",
        choices=["driver", "passenger", "both"],
        default="both",
        help="Side to process. Default: both.",
    )
    parser.add_argument(
        "--max-elements-per-side",
        type=int,
        default=6,
        help="Maximum number of mapped elements to keep per side.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        input_json = resolve_path(args.input_json)
        out_json = resolve_path(args.out_json)
        out_hints_json = resolve_path(args.out_hints_json) if args.out_hints_json else None

        if not input_json.is_file():
            raise FileNotFoundError(f"Input JSON not found: {input_json}")
        if args.max_elements_per_side <= 0:
            raise ValueError("--max-elements-per-side must be a positive integer.")

        with input_json.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        records = parse_records(payload)
        if not records:
            raise ValueError("No valid object records found in input JSON.")

        sides = list(VALID_SIDES) if args.side == "both" else [args.side]
        image_results: list[dict[str, Any]] = []
        hints_results: list[dict[str, Any]] = []

        for index, record in enumerate(records, start=1):
            image_name = first_text(record, "image_name", "image_id", "name") or f"item_{index:03d}"
            side_descriptions = resolve_side_descriptions(record, args.side)

            side_outputs: list[dict[str, Any]] = []
            side_hints: dict[str, list[dict[str, str]]] = {}
            for side in sides:
                side_result = build_side_result(
                    side=side,
                    description=side_descriptions.get(side, ""),
                    max_elements=args.max_elements_per_side,
                )
                side_outputs.append(side_result)
                side_hints[side] = side_result["hints"]

            image_results.append(
                {
                    "image_name": image_name,
                    "sides": side_outputs,
                }
            )
            hints_results.append({"image_name": image_name, "hints_by_side": side_hints})

        output_payload = {
            "images": image_results,
            "settings": {
                "side_mode": args.side,
                "max_elements_per_side": int(args.max_elements_per_side),
                "input_json": str(input_json),
            },
        }

        out_json.parent.mkdir(parents=True, exist_ok=True)
        with out_json.open("w", encoding="utf-8") as handle:
            json.dump(output_payload, handle, indent=2)
            handle.write("\n")

        if out_hints_json:
            hints_payload: dict[str, Any]
            if len(hints_results) == 1:
                hints_payload = hints_results[0]["hints_by_side"]
            else:
                hints_payload = {"images": hints_results}

            out_hints_json.parent.mkdir(parents=True, exist_ok=True)
            with out_hints_json.open("w", encoding="utf-8") as handle:
                json.dump(hints_payload, handle, indent=2)
                handle.write("\n")

        print(f"Wrote description mapping JSON: {out_json}")
        if out_hints_json:
            print(f"Wrote hints JSON: {out_hints_json}")
        print(f"Processed description records: {len(image_results)}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
