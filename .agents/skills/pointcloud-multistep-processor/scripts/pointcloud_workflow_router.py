#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEMO_DEFAULTS = {
    "las": "data/point_cloud/cloud_test.las",
    "outdir": "artifacts/pointcloud_workflows",
    "reference_class": "road",
    "distance_backend": "auto",
}

MODE_ALIASES = {
    "segment": "segment",
    "segmentation": "segment",
    "cluster": "cluster",
    "clustering": "cluster",
    "distance": "distance",
    "distances": "distance",
    "roadside_distance_to_road": "roadside_distance_to_road",
    "roadside-distance": "roadside_distance_to_road",
    "object_to_road_distance": "roadside_distance_to_road",
}

GLOBAL_SETTING_KEYS = {
    "las",
    "outdir",
    "run_id",
    "reference_class",
    "distance_backend",
    "segmentation_metadata",
    "trajectory",
    "segment_prefix",
    "segment_outdir",
    "out_las",
    "segment_flags",
    "cluster_outdir",
    "cluster_prefix",
    "distance_threshold_m",
    "min_cluster_size",
    "cluster_backend",
    "cluster_flags",
    "indices",
    "indices_file",
    "visualize_segmented_cloud",
    "visualization_backend",
    "visualization_flags",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Route multi-step 3D point-cloud workflows "
            "(segment, cluster, distance, roadside_distance_to_road)"
        )
    )
    parser.add_argument("--input-json", required=True, help="Input workflow JSON path")
    parser.add_argument("--out-json", default=None, help="Optional output JSON path")
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Python executable used to call repository scripts",
    )
    return parser.parse_args()


def find_repo_root(anchor: Path) -> Path:
    required = [
        Path("scripts/segment_road_cloud.py"),
        Path("scripts/pointcloud/cluster_euclidean.py"),
        Path("scripts/pointcloud/min_cluster_distance.py"),
        Path("scripts/visualize_segmented_cloud.py"),
    ]
    for candidate in [anchor.resolve(), *anchor.resolve().parents]:
        if all((candidate / rel).exists() for rel in required):
            return candidate
    raise FileNotFoundError("Could not locate repository root with point-cloud scripts")


def merge_settings(payload: dict[str, Any]) -> dict[str, Any]:
    settings: dict[str, Any] = dict(DEMO_DEFAULTS)
    defaults = payload.get("defaults")
    if isinstance(defaults, dict):
        settings.update(defaults)
    for key in GLOBAL_SETTING_KEYS:
        if key in payload:
            settings[key] = payload[key]
    return settings


def normalize_mode(value: str) -> str:
    key = value.strip().lower()
    if key not in MODE_ALIASES:
        raise ValueError(f"Unsupported mode '{value}'")
    return MODE_ALIASES[key]


def detect_mode(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("mode"), str):
        return normalize_mode(payload["mode"])

    if isinstance(payload.get("objects"), list) or isinstance(payload.get("items"), list):
        if "pairs" not in payload and "cluster" not in payload:
            return "roadside_distance_to_road"
    if isinstance(payload.get("pairs"), list):
        return "distance"
    if "distance_threshold_m" in payload or "min_cluster_size" in payload:
        return "cluster"
    if "segment_flags" in payload or "trajectory" in payload:
        return "segment"

    raise ValueError(
        "Cannot infer mode. Provide mode as one of: "
        "segment, cluster, distance, roadside_distance_to_road"
    )


def resolve_path(path_value: str | Path, repo_root: Path, base_dir: Path | None = None) -> Path:
    path = Path(str(path_value))
    if path.is_absolute():
        return path.resolve()
    if base_dir is not None:
        return (base_dir / path).resolve()
    return (repo_root / path).resolve()


def json_from_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("Script returned empty stdout")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("Expected JSON object in stdout")
    except json.JSONDecodeError:
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            parsed = json.loads(text[first : last + 1])
            if isinstance(parsed, dict):
                return parsed
    raise ValueError("Script stdout did not contain a valid JSON object")


def read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in: {path}")
    return data


def parse_indices_value(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(v) for v in value]
    if isinstance(value, tuple):
        return [int(v) for v in value]
    if isinstance(value, str):
        tokens = [tok for tok in re.split(r"[\s,]+", value.strip()) if tok]
        return [int(tok) for tok in tokens]
    raise ValueError("indices must be list[int], tuple[int], or comma/space separated string")


def write_indices_file(indices: list[int], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(int(idx)) for idx in indices) + "\n", encoding="utf-8")
    return path.resolve()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        key = value.strip().lower()
        if key in {"1", "true", "yes", "on"}:
            return True
        if key in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def append_cli_flags(command: list[str], flags: Any) -> None:
    if not isinstance(flags, dict):
        return
    for raw_key in sorted(flags):
        value = flags[raw_key]
        if value is None:
            continue
        flag = "--" + str(raw_key).strip().replace("_", "-")
        command.extend([flag, str(value)])


def call_json_command(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode != 0:
        error_text = proc.stderr.strip() or proc.stdout.strip() or "Unknown error"
        raise RuntimeError(error_text)
    return json_from_stdout(proc.stdout)


def call_text_command(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": int(proc.returncode),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def build_run_layout(base_outdir: Path, run_id: Any) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if isinstance(run_id, str) and run_id.strip():
        rid = run_id.strip()
    else:
        rid = f"run_{timestamp}_{uuid.uuid4().hex[:8]}"
    run_dir = (base_outdir / rid).resolve()
    inputs_dir = run_dir / "inputs"
    steps_dir = run_dir / "steps"
    run_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    steps_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_id": rid,
        "run_dir": run_dir,
        "inputs_dir": inputs_dir,
        "steps_dir": steps_dir,
    }


def resolve_cluster_indices_path(
    cluster_spec: dict[str, Any],
    repo_root: Path,
) -> tuple[Path, dict[str, Any]]:
    manifest_value = cluster_spec.get("manifest", cluster_spec.get("clusters_manifest"))
    cluster_id_value = cluster_spec.get("cluster_id")
    if manifest_value is None or cluster_id_value is None:
        raise ValueError("cluster source requires 'manifest' (or 'clusters_manifest') and 'cluster_id'")

    manifest_path = resolve_path(str(manifest_value), repo_root)
    manifest = read_json_object(manifest_path)
    clusters = manifest.get("clusters")
    if not isinstance(clusters, list):
        raise ValueError(f"Invalid clusters manifest (missing list): {manifest_path}")

    target_id = int(cluster_id_value)
    selected_entry: dict[str, Any] | None = None
    for entry in clusters:
        if isinstance(entry, dict) and int(entry.get("cluster_id", -1)) == target_id:
            selected_entry = entry
            break
    if selected_entry is None:
        raise KeyError(f"Cluster id {target_id} not found in manifest: {manifest_path}")

    idx_value = selected_entry.get("indices_path")
    if not isinstance(idx_value, str) or not idx_value.strip():
        raise ValueError(f"Cluster entry missing indices_path for cluster_id={target_id}")

    idx_path = resolve_path(idx_value, repo_root, base_dir=manifest_path.parent)
    if not idx_path.exists():
        raise FileNotFoundError(f"Cluster indices file not found: {idx_path}")

    source = {
        "mode": "cluster_manifest",
        "manifest_path": str(manifest_path),
        "cluster_id": target_id,
        "indices_file": str(idx_path),
    }
    return idx_path, source


def resolve_object_source(
    item: dict[str, Any],
    repo_root: Path,
    inputs_dir: Path,
    file_tag: str,
) -> tuple[Path, dict[str, Any]]:
    has_inline = "indices" in item
    has_file = "indices_file" in item
    has_cluster = "cluster" in item
    source_count = int(has_inline) + int(has_file) + int(has_cluster)
    if source_count != 1:
        raise ValueError("Each object must provide exactly one of: indices, indices_file, cluster")

    if has_inline:
        parsed = parse_indices_value(item["indices"])
        out_path = write_indices_file(parsed, inputs_dir / f"{file_tag}.indices.txt")
        return out_path, {
            "mode": "inline_indices",
            "count": len(parsed),
            "generated_indices_file": str(out_path),
        }

    if has_file:
        path = resolve_path(str(item["indices_file"]), repo_root)
        if not path.exists():
            raise FileNotFoundError(f"indices_file not found: {path}")
        return path, {"mode": "indices_file", "indices_file": str(path)}

    cluster_value = item.get("cluster")
    if not isinstance(cluster_value, dict):
        raise ValueError("cluster source must be an object with manifest and cluster_id")
    return resolve_cluster_indices_path(cluster_value, repo_root)


def resolve_pair_source(
    pair: dict[str, Any],
    side: str,
    repo_root: Path,
    inputs_dir: Path,
    file_tag: str,
) -> tuple[Path, dict[str, Any]]:
    if side not in {"a", "b"}:
        raise ValueError("side must be 'a' or 'b'")

    inline_key = f"indices_{side}"
    file_key = f"indices_{side}_file"
    cluster_key = f"cluster_{side}"
    cluster_id_key = f"cluster_{side}_id"

    has_inline = inline_key in pair
    has_file = file_key in pair
    has_cluster_dict = cluster_key in pair
    has_shared_cluster = ("clusters_manifest" in pair) and (cluster_id_key in pair)
    has_cluster = has_cluster_dict or has_shared_cluster

    source_count = int(has_inline) + int(has_file) + int(has_cluster)
    if source_count != 1:
        raise ValueError(
            f"Pair source for side '{side}' must provide exactly one of "
            f"{inline_key}, {file_key}, {cluster_key} or clusters_manifest+{cluster_id_key}"
        )

    if has_inline:
        parsed = parse_indices_value(pair[inline_key])
        out_path = write_indices_file(parsed, inputs_dir / f"{file_tag}.indices_{side}.txt")
        return out_path, {
            "mode": "inline_indices",
            "count": len(parsed),
            "generated_indices_file": str(out_path),
        }

    if has_file:
        path = resolve_path(str(pair[file_key]), repo_root)
        if not path.exists():
            raise FileNotFoundError(f"{file_key} not found: {path}")
        return path, {"mode": "indices_file", "indices_file": str(path)}

    if has_cluster_dict:
        cluster_value = pair.get(cluster_key)
        if not isinstance(cluster_value, dict):
            raise ValueError(f"{cluster_key} must be an object")
        return resolve_cluster_indices_path(cluster_value, repo_root)

    cluster_spec = {
        "manifest": pair["clusters_manifest"],
        "cluster_id": pair[cluster_id_key],
    }
    return resolve_cluster_indices_path(cluster_spec, repo_root)


def run_segmentation_step(
    settings: dict[str, Any],
    repo_root: Path,
    python_bin: str,
    run_dir: Path,
) -> dict[str, Any]:
    reuse_metadata = settings.get("segmentation_metadata")
    if reuse_metadata is not None:
        metadata_path = resolve_path(str(reuse_metadata), repo_root)
        if not metadata_path.exists():
            raise FileNotFoundError(f"segmentation_metadata not found: {metadata_path}")
        metadata = read_json_object(metadata_path)
        return {
            "mode": "reuse",
            "metadata_path": str(metadata_path),
            "metadata": metadata,
            "command": None,
            "result": None,
        }

    las_path = resolve_path(str(settings.get("las", DEMO_DEFAULTS["las"])), repo_root)
    outdir_value = settings.get("segment_outdir")
    if outdir_value is None:
        outdir = run_dir / "segmentation"
    else:
        outdir = resolve_path(str(outdir_value), repo_root)

    out_prefix = str(settings.get("segment_prefix", "segmented_cloud"))

    command = [
        python_bin,
        str(repo_root / "scripts" / "segment_road_cloud.py"),
        "--las",
        str(las_path),
        "--outdir",
        str(outdir),
        "--out-prefix",
        out_prefix,
    ]

    trajectory = settings.get("trajectory")
    if trajectory is not None:
        command.extend(["--trajectory", str(resolve_path(str(trajectory), repo_root))])

    out_las = settings.get("out_las")
    if out_las is not None:
        command.extend(["--out-las", str(resolve_path(str(out_las), repo_root))])

    append_cli_flags(command, settings.get("segment_flags"))

    result = call_json_command(command)
    metadata_path_value = result.get("metadata_path")
    if not isinstance(metadata_path_value, str) or not metadata_path_value.strip():
        raise ValueError("Segmentation output did not include metadata_path")
    metadata_path = resolve_path(metadata_path_value, repo_root)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Segmentation metadata path not found: {metadata_path}")
    metadata = read_json_object(metadata_path)

    return {
        "mode": "executed",
        "metadata_path": str(metadata_path),
        "metadata": metadata,
        "command": command,
        "result": result,
    }


def extract_class_indices_path(
    metadata: dict[str, Any],
    metadata_path: Path,
    reference_class: str,
    repo_root: Path,
) -> Path:
    class_indices = metadata.get("class_indices")
    if not isinstance(class_indices, dict):
        raise ValueError("Segmentation metadata missing class_indices map")

    entry = class_indices.get(reference_class)
    if not isinstance(entry, dict):
        raise ValueError(f"reference_class '{reference_class}' not found in class_indices")

    path_value = entry.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError(f"class_indices['{reference_class}'] missing path")

    idx_path = resolve_path(path_value, repo_root, base_dir=metadata_path.parent)
    if not idx_path.exists():
        raise FileNotFoundError(f"Reference indices path not found: {idx_path}")
    return idx_path


def run_cluster_step(
    settings: dict[str, Any],
    repo_root: Path,
    python_bin: str,
    run_dir: Path,
    inputs_dir: Path,
) -> dict[str, Any]:
    las_path = resolve_path(str(settings.get("las", DEMO_DEFAULTS["las"])), repo_root)

    outdir_value = settings.get("cluster_outdir")
    if outdir_value is None:
        outdir = run_dir / "clusters"
    else:
        outdir = resolve_path(str(outdir_value), repo_root)
    outdir.mkdir(parents=True, exist_ok=True)

    out_prefix = str(settings.get("cluster_prefix", "euclid_clusters"))

    command = [
        python_bin,
        str(repo_root / "scripts" / "pointcloud" / "cluster_euclidean.py"),
        "--las",
        str(las_path),
        "--outdir",
        str(outdir),
        "--out-prefix",
        out_prefix,
    ]

    has_inline = "indices" in settings
    has_file = "indices_file" in settings
    if has_inline and has_file:
        raise ValueError("Cluster mode accepts either indices or indices_file, not both")

    candidate_source: dict[str, Any] = {"mode": "all_points"}
    if has_inline:
        parsed = parse_indices_value(settings["indices"])
        generated = write_indices_file(parsed, inputs_dir / f"{out_prefix}.candidate_indices.txt")
        command.extend(["--indices-file", str(generated)])
        candidate_source = {
            "mode": "inline_indices",
            "count": len(parsed),
            "generated_indices_file": str(generated),
        }
    elif has_file:
        idx_path = resolve_path(str(settings["indices_file"]), repo_root)
        if not idx_path.exists():
            raise FileNotFoundError(f"indices_file not found: {idx_path}")
        command.extend(["--indices-file", str(idx_path)])
        candidate_source = {"mode": "indices_file", "indices_file": str(idx_path)}

    if "distance_threshold_m" in settings:
        command.extend(["--distance-threshold-m", str(settings["distance_threshold_m"])])
    if "min_cluster_size" in settings:
        command.extend(["--min-cluster-size", str(settings["min_cluster_size"])])
    if "cluster_backend" in settings:
        command.extend(["--backend", str(settings["cluster_backend"])])

    append_cli_flags(command, settings.get("cluster_flags"))

    result = call_json_command(command)
    return {
        "command": command,
        "candidate_source": candidate_source,
        "result": result,
    }


def run_distance_pairs(
    pairs: list[Any],
    las_path: Path,
    default_backend: str,
    repo_root: Path,
    python_bin: str,
    inputs_dir: Path,
) -> list[dict[str, Any]]:
    script = repo_root / "scripts" / "pointcloud" / "min_cluster_distance.py"
    results: list[dict[str, Any]] = []

    for idx, raw_pair in enumerate(pairs):
        pair = dict(raw_pair) if isinstance(raw_pair, dict) else {"indices_a": raw_pair}
        trace = {"item_index": idx, "input": raw_pair}
        try:
            src_a_path, src_a = resolve_pair_source(pair, "a", repo_root, inputs_dir, f"pair_{idx:04d}")
            src_b_path, src_b = resolve_pair_source(pair, "b", repo_root, inputs_dir, f"pair_{idx:04d}")

            backend = str(pair.get("backend", default_backend))
            command = [
                python_bin,
                str(script),
                "--las",
                str(las_path),
                "--indices-a-file",
                str(src_a_path),
                "--indices-b-file",
                str(src_b_path),
                "--backend",
                backend,
            ]

            distance_out = call_json_command(command)
            results.append(
                {
                    "trace": trace,
                    "resolved_sources": {"a": src_a, "b": src_b},
                    **distance_out,
                }
            )
        except Exception as exc:
            results.append({"trace": trace, "error": str(exc)})

    return results


def maybe_run_visualization(
    settings: dict[str, Any],
    repo_root: Path,
    python_bin: str,
    las_path: Path,
    labels_path: Path,
) -> dict[str, Any]:
    if not as_bool(settings.get("visualize_segmented_cloud", False)):
        return {"requested": False}

    backend = str(settings.get("visualization_backend", "open3d"))
    command = [
        python_bin,
        str(repo_root / "scripts" / "visualize_segmented_cloud.py"),
        "--las",
        str(las_path),
        "--labels",
        str(labels_path),
        "--backend",
        backend,
    ]
    append_cli_flags(command, settings.get("visualization_flags"))
    result = call_text_command(command)

    if int(result["returncode"]) == 0:
        return {"requested": True, "status": "ok", **result}
    return {"requested": True, "status": "error", **result}


def run_segment_mode(
    payload: dict[str, Any],
    settings: dict[str, Any],
    repo_root: Path,
    python_bin: str,
    run_dir: Path,
) -> dict[str, Any]:
    segment_settings = dict(settings)
    segment_block = payload.get("segment")
    if isinstance(segment_block, dict):
        segment_settings.update(segment_block)

    step = run_segmentation_step(segment_settings, repo_root, python_bin, run_dir)
    metadata = step["metadata"]

    return {
        "segmentation": {
            "mode": step["mode"],
            "metadata_path": step["metadata_path"],
            "class_counts": metadata.get("class_counts"),
            "class_indices": metadata.get("class_indices"),
            "labels_path": metadata.get("labels_path"),
            "point_count_processed": metadata.get("point_count_processed"),
            "command": step["command"],
            "raw_result": step["result"],
        }
    }


def run_cluster_mode(
    payload: dict[str, Any],
    settings: dict[str, Any],
    repo_root: Path,
    python_bin: str,
    run_dir: Path,
    inputs_dir: Path,
) -> dict[str, Any]:
    cluster_settings = dict(settings)
    cluster_block = payload.get("cluster")
    if isinstance(cluster_block, dict):
        cluster_settings.update(cluster_block)

    step = run_cluster_step(cluster_settings, repo_root, python_bin, run_dir, inputs_dir)
    return {"clustering": step}


def run_distance_mode(
    payload: dict[str, Any],
    settings: dict[str, Any],
    repo_root: Path,
    python_bin: str,
    inputs_dir: Path,
) -> dict[str, Any]:
    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Distance mode requires non-empty 'pairs' list")

    las_path = resolve_path(str(settings.get("las", DEMO_DEFAULTS["las"])), repo_root)
    backend = str(settings.get("distance_backend", DEMO_DEFAULTS["distance_backend"]))

    results = run_distance_pairs(
        pairs=pairs,
        las_path=las_path,
        default_backend=backend,
        repo_root=repo_root,
        python_bin=python_bin,
        inputs_dir=inputs_dir,
    )
    return {
        "las_path": str(las_path),
        "result_count": len(results),
        "results": results,
    }


def run_roadside_mode(
    payload: dict[str, Any],
    settings: dict[str, Any],
    repo_root: Path,
    python_bin: str,
    run_dir: Path,
    inputs_dir: Path,
) -> dict[str, Any]:
    object_list = payload.get("objects")
    if object_list is None:
        object_list = payload.get("items")
    if not isinstance(object_list, list) or not object_list:
        raise ValueError("roadside_distance_to_road mode requires non-empty 'objects' (or 'items') list")

    segment_settings = dict(settings)
    segment_block = payload.get("segment")
    if isinstance(segment_block, dict):
        segment_settings.update(segment_block)

    segmentation = run_segmentation_step(segment_settings, repo_root, python_bin, run_dir)
    metadata = segmentation["metadata"]
    metadata_path = Path(segmentation["metadata_path"])

    las_value = metadata.get("input_las", settings.get("las", DEMO_DEFAULTS["las"]))
    las_path = resolve_path(str(las_value), repo_root)

    reference_class = str(settings.get("reference_class", DEMO_DEFAULTS["reference_class"])).strip().lower()
    if reference_class not in {"road", "ground", "not-ground"}:
        raise ValueError("reference_class must be one of: road, ground, not-ground")

    reference_indices_path = extract_class_indices_path(
        metadata=metadata,
        metadata_path=metadata_path,
        reference_class=reference_class,
        repo_root=repo_root,
    )

    default_backend = str(settings.get("distance_backend", DEMO_DEFAULTS["distance_backend"]))
    script = repo_root / "scripts" / "pointcloud" / "min_cluster_distance.py"
    results: list[dict[str, Any]] = []

    for idx, raw_item in enumerate(object_list):
        item = dict(raw_item) if isinstance(raw_item, dict) else {"indices": raw_item}
        trace = {"item_index": idx, "input": raw_item}
        try:
            source_path, source_meta = resolve_object_source(
                item=item,
                repo_root=repo_root,
                inputs_dir=inputs_dir,
                file_tag=f"object_{idx:04d}",
            )
            backend = str(item.get("backend", default_backend))
            command = [
                python_bin,
                str(script),
                "--las",
                str(las_path),
                "--indices-a-file",
                str(source_path),
                "--indices-b-file",
                str(reference_indices_path),
                "--backend",
                backend,
            ]
            distance_out = call_json_command(command)
            results.append(
                {
                    "trace": trace,
                    "reference_class": reference_class,
                    "reference_indices_file": str(reference_indices_path),
                    "resolved_source": source_meta,
                    **distance_out,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "trace": trace,
                    "reference_class": reference_class,
                    "reference_indices_file": str(reference_indices_path),
                    "error": str(exc),
                }
            )

    labels_value = metadata.get("labels_path")
    labels_path = (
        resolve_path(str(labels_value), repo_root, base_dir=metadata_path.parent)
        if isinstance(labels_value, str)
        else None
    )
    if labels_path is None:
        visualization = {"requested": False, "reason": "labels_path missing in segmentation metadata"}
    elif not labels_path.exists():
        visualization = {"requested": False, "reason": f"labels_path not found: {labels_path}"}
    else:
        visualization = maybe_run_visualization(settings, repo_root, python_bin, las_path, labels_path)

    return {
        "las_path": str(las_path),
        "reference_class": reference_class,
        "reference_indices_file": str(reference_indices_path),
        "segmentation": {
            "mode": segmentation["mode"],
            "metadata_path": segmentation["metadata_path"],
            "class_counts": metadata.get("class_counts"),
            "class_indices": metadata.get("class_indices"),
            "labels_path": metadata.get("labels_path"),
            "command": segmentation["command"],
            "raw_result": segmentation["result"],
        },
        "visualization": visualization,
        "result_count": len(results),
        "results": results,
    }


def main() -> None:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__))
    input_json_path = resolve_path(args.input_json, repo_root)
    payload = read_json_object(input_json_path)

    settings = merge_settings(payload)
    mode = detect_mode(payload)

    outdir = resolve_path(str(settings.get("outdir", DEMO_DEFAULTS["outdir"])), repo_root)
    layout = build_run_layout(outdir, settings.get("run_id"))
    run_dir = Path(layout["run_dir"])
    inputs_dir = Path(layout["inputs_dir"])

    if mode == "segment":
        mode_output = run_segment_mode(payload, settings, repo_root, args.python_bin, run_dir)
    elif mode == "cluster":
        mode_output = run_cluster_mode(payload, settings, repo_root, args.python_bin, run_dir, inputs_dir)
    elif mode == "distance":
        mode_output = run_distance_mode(payload, settings, repo_root, args.python_bin, inputs_dir)
    else:
        mode_output = run_roadside_mode(payload, settings, repo_root, args.python_bin, run_dir, inputs_dir)

    output: dict[str, Any] = {
        "mode": mode,
        "input_json": str(input_json_path),
        "defaults": DEMO_DEFAULTS,
        "run": {
            "run_id": str(layout["run_id"]),
            "run_dir": str(layout["run_dir"]),
            "inputs_dir": str(layout["inputs_dir"]),
            "steps_dir": str(layout["steps_dir"]),
            "repo_root": str(repo_root),
        },
        **mode_output,
    }

    text = json.dumps(output, indent=2)
    print(text)

    if args.out_json:
        out_path = resolve_path(args.out_json, repo_root)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
