#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

DEMO_DEFAULTS = {
    "poses": "data/Trajectories/01_N3.CSV",
    "extrinsics": "data/Calibration/calib1.xml",
    "las": "data/point_cloud/cloud_test.las",
    "image": "data/images/ladybug_13185920_20200219_095143_Portugal_000_Panoramic_108.png",
    "image_id": "ladybug_panoramic_000108.jpg",
}

COMMON_KEYS = {
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
}

BBOX_KEYS = {"max_distance_m", "min_intensity", "out_las"}
POINT_KEYS = {"indices", "indices_file", "use_full_cloud"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Route projection requests between bbox_to_points.py and points_to_bbox.py"
    )
    parser.add_argument("--input-json", required=True, help="Input request JSON")
    parser.add_argument("--out-json", default=None, help="Optional output JSON path")
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Python executable used to call repository projection scripts",
    )
    return parser.parse_args()


def find_repo_root(anchor: Path) -> Path:
    candidates = [anchor.resolve(), *anchor.resolve().parents]
    for path in candidates:
        if (path / "scripts" / "bbox_to_points.py").exists() and (
            path / "scripts" / "points_to_bbox.py"
        ).exists():
            return path
    raise FileNotFoundError("Could not find repository root with projection scripts")


def normalize_mode(value: str) -> str:
    aliases = {
        "bbox_to_points": "bbox_to_points",
        "2d_to_3d": "bbox_to_points",
        "bbox->points": "bbox_to_points",
        "points_to_bbox": "points_to_bbox",
        "3d_to_2d": "points_to_bbox",
        "points->bbox": "points_to_bbox",
    }
    key = value.strip().lower()
    if key not in aliases:
        raise ValueError(f"Unsupported mode '{value}'")
    return aliases[key]


def detect_mode(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("mode"), str):
        return normalize_mode(payload["mode"])

    if any(k in payload for k in ("bboxes", "bbox")):
        return "bbox_to_points"
    if any(k in payload for k in ("indices", "indices_file", "use_full_cloud")):
        return "points_to_bbox"

    items = payload.get("items")
    if isinstance(items, list) and items:
        for item in items:
            if not isinstance(item, dict):
                continue
            if any(k in item for k in ("bbox", "bboxes")):
                return "bbox_to_points"
            if any(k in item for k in ("indices", "indices_file", "use_full_cloud")):
                return "points_to_bbox"

    raise ValueError(
        "Cannot infer mode. Provide mode='bbox_to_points' or mode='points_to_bbox'"
    )


def json_from_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("Projection script returned empty stdout")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            return json.loads(text[first : last + 1])
    raise ValueError("Projection script stdout did not contain valid JSON")


def as_bool_text(value: Any, default: str = "true") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text in {"true", "false"}:
        return text
    raise ValueError(f"Expected true/false value, got '{value}'")


def resolve_path(path_value: str, repo_root: Path) -> str:
    path = Path(path_value)
    return str(path if path.is_absolute() else (repo_root / path).resolve())


def bbox_as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return ",".join(str(int(v)) for v in value)
    raise ValueError("bbox must be 'x1,y1,x2,y2' or [x1,y1,x2,y2]")


def parse_indices(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(v) for v in value]
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace("\n", ",").split(",") if p.strip()]
        return [int(p) for p in parts]
    raise ValueError("indices must be a list[int] or comma-separated string")


def write_indices_file(indices: list[int]) -> Path:
    temp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    with temp:
        for idx in indices:
            temp.write(f"{int(idx)}\n")
    return Path(temp.name)


def write_full_cloud_indices_file(las_path: Path) -> tuple[Path, int]:
    try:
        import laspy  # type: ignore
    except ImportError as exc:
        raise RuntimeError("laspy is required when use_full_cloud=true") from exc

    with laspy.open(str(las_path)) as reader:
        count = int(reader.header.point_count)

    temp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    with temp:
        for idx in range(count):
            temp.write(f"{idx}\n")
    return Path(temp.name), count


def call_projection(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode != 0:
        error_text = proc.stderr.strip() or proc.stdout.strip() or "Unknown error"
        raise RuntimeError(error_text)
    return json_from_stdout(proc.stdout)


def collect_settings(payload: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    settings: dict[str, Any] = dict(DEMO_DEFAULTS)

    defaults = payload.get("defaults")
    if isinstance(defaults, dict):
        settings.update(defaults)

    for key in COMMON_KEYS | BBOX_KEYS | POINT_KEYS:
        if key in payload:
            settings[key] = payload[key]
    for key in COMMON_KEYS | BBOX_KEYS | POINT_KEYS:
        if key in item:
            settings[key] = item[key]
    return settings


def collect_bbox_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("items"), list):
        return [dict(v) if isinstance(v, dict) else {"bbox": v} for v in payload["items"]]

    if isinstance(payload.get("bboxes"), list):
        items: list[dict[str, Any]] = []
        for entry in payload["bboxes"]:
            if isinstance(entry, dict):
                items.append(dict(entry))
            else:
                items.append({"bbox": entry})
        return items

    if "bbox" in payload:
        if isinstance(payload["bbox"], dict):
            return [dict(payload["bbox"])]
        return [{"bbox": payload["bbox"]}]

    raise ValueError("bbox_to_points mode requires bbox, bboxes, or items")


def collect_points_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("items"), list):
        return [dict(v) if isinstance(v, dict) else {"indices": v} for v in payload["items"]]

    has_points_keys = any(k in payload for k in ("indices", "indices_file", "use_full_cloud"))
    if has_points_keys:
        return [dict(payload)]

    raise ValueError("points_to_bbox mode requires indices/indices_file/use_full_cloud or items")


def base_required_args(settings: dict[str, Any], repo_root: Path) -> list[str]:
    return [
        "--poses",
        resolve_path(str(settings["poses"]), repo_root),
        "--extrinsics",
        resolve_path(str(settings["extrinsics"]), repo_root),
        "--las",
        resolve_path(str(settings["las"]), repo_root),
        "--image",
        resolve_path(str(settings["image"]), repo_root),
        "--image-id",
        str(settings["image_id"]),
    ]


def add_opt(command: list[str], flag: str, value: Any) -> None:
    if value is None:
        return
    command.extend([flag, str(value)])


def run_bbox_mode(
    payload: dict[str, Any], repo_root: Path, python_bin: str
) -> list[dict[str, Any]]:
    script = repo_root / "scripts" / "bbox_to_points.py"
    items = collect_bbox_items(payload)
    results: list[dict[str, Any]] = []

    for idx, raw in enumerate(items):
        item = dict(raw)
        trace = {"item_index": idx, "input": raw}
        try:
            settings = collect_settings(payload, item)
            if "bbox" not in item:
                raise ValueError("Each bbox item must include 'bbox'")

            command = [python_bin, str(script), *base_required_args(settings, repo_root)]
            command.extend(["--bbox", bbox_as_text(item["bbox"])])
            add_opt(command, "--max-distance-m", settings.get("max_distance_m"))
            add_opt(command, "--min-intensity", settings.get("min_intensity"))
            if settings.get("out_las"):
                add_opt(command, "--out-las", resolve_path(str(settings["out_las"]), repo_root))
            add_opt(command, "--pose-model", settings.get("pose_model"))
            add_opt(
                command,
                "--invert-extrinsics",
                as_bool_text(settings.get("invert_extrinsics"), default="true"),
            )
            add_opt(
                command,
                "--flip-pano-u",
                as_bool_text(settings.get("flip_pano_u"), default="true"),
            )
            add_opt(command, "--v-top", settings.get("v_top"))
            add_opt(command, "--v-bottom", settings.get("v_bottom"))

            if bool(settings.get("visualize")):
                command.append("--visualize")
            if settings.get("visualization_out"):
                add_opt(
                    command,
                    "--visualization-out",
                    resolve_path(str(settings["visualization_out"]), repo_root),
                )

            output = call_projection(command)
            results.append({"trace": trace, **output})
        except Exception as exc:
            results.append({"trace": trace, "error": str(exc)})

    return results


def run_points_mode(
    payload: dict[str, Any], repo_root: Path, python_bin: str
) -> list[dict[str, Any]]:
    script = repo_root / "scripts" / "points_to_bbox.py"
    items = collect_points_items(payload)
    results: list[dict[str, Any]] = []

    for idx, raw in enumerate(items):
        item = dict(raw)
        trace = {"item_index": idx, "input": raw}
        temporary_files: list[Path] = []
        try:
            settings = collect_settings(payload, item)
            command = [python_bin, str(script), *base_required_args(settings, repo_root)]
            add_opt(command, "--pose-model", settings.get("pose_model"))
            add_opt(
                command,
                "--invert-extrinsics",
                as_bool_text(settings.get("invert_extrinsics"), default="true"),
            )
            add_opt(
                command,
                "--flip-pano-u",
                as_bool_text(settings.get("flip_pano_u"), default="true"),
            )
            add_opt(command, "--v-top", settings.get("v_top"))
            add_opt(command, "--v-bottom", settings.get("v_bottom"))

            has_indices = "indices" in item
            has_indices_file = "indices_file" in item
            use_full_cloud = bool(item.get("use_full_cloud", False))
            sources = int(has_indices) + int(has_indices_file) + int(use_full_cloud)
            if sources != 1:
                raise ValueError(
                    "Provide exactly one of indices, indices_file, or use_full_cloud=true"
                )

            if has_indices:
                indices = parse_indices(item["indices"])
                temp_file = write_indices_file(indices)
                temporary_files.append(temp_file)
                command.extend(["--indices-file", str(temp_file)])
            elif has_indices_file:
                indices_path = resolve_path(str(item["indices_file"]), repo_root)
                command.extend(["--indices-file", indices_path])
            else:
                las_path = Path(resolve_path(str(settings["las"]), repo_root))
                temp_file, point_count = write_full_cloud_indices_file(las_path)
                temporary_files.append(temp_file)
                trace["full_cloud_point_count"] = point_count
                command.extend(["--indices-file", str(temp_file)])

            if bool(settings.get("visualize")):
                command.append("--visualize")
            if settings.get("visualization_out"):
                add_opt(
                    command,
                    "--visualization-out",
                    resolve_path(str(settings["visualization_out"]), repo_root),
                )

            output = call_projection(command)
            results.append({"trace": trace, **output})
        except Exception as exc:
            results.append({"trace": trace, "error": str(exc)})
        finally:
            for temp_file in temporary_files:
                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass

    return results


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_json).resolve()
    repo_root = find_repo_root(Path(__file__))

    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object")

    mode = detect_mode(payload)
    if mode == "bbox_to_points":
        results = run_bbox_mode(payload, repo_root, args.python_bin)
    else:
        results = run_points_mode(payload, repo_root, args.python_bin)

    output = {
        "mode": mode,
        "demo_defaults": DEMO_DEFAULTS,
        "result_count": len(results),
        "results": results,
    }
    text = json.dumps(output, indent=2)
    print(text)

    if args.out_json:
        out_path = Path(args.out_json).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
