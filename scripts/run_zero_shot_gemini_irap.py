#!/usr/bin/env python
"""Run zero-shot Gemini vision coding for the selected 17 iRAP attributes.

Reads GEMINI_API_KEY from the environment or from .venv/.env by default.
This script intentionally reads only image files and fixed category schemas.
It does not read GroundTruth.csv, images-labeling-coding.xlsx, or any label file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from run_zero_shot_openai_irap import (
    ATTRIBUTES,
    CATEGORIES,
    IRAP_EXPORT_ATTRIBUTES,
    attr_slug,
    encode_image,
    folder_name,
    image_id,
    list_images,
    parse_json_object,
    save_results,
    validate_record,
)
from zero_shot_common_prompt import PROMPT_PATH, PROMPT_VERSION, build_common_prompt, prompt_sha256


DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_RUN_ID = f"zero_shot_gemini35_flash_lite_common_prompt_v1_{datetime.now().strftime('%Y-%m-%d')}"


def method_for_model(model: str) -> str:
    model_slug = re.sub(r"[^a-z0-9]+", "", model.lower())
    return f"zero_shot_irap_17attr_frozen_common_prompt_v1_{model_slug}_visual_only"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def call_gemini(prompt: str, image_b64: str, api_key: str, timeout: int, model: str) -> str:
    quoted_model = urllib.parse.quote(model, safe="")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{quoted_model}:generateContent?key={urllib.parse.quote(api_key)}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "maxOutputTokens": 4000,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {body}") from exc

    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response: {data}") from exc

    chunks = [part.get("text", "") for part in parts if "text" in part]
    return "\n".join(chunks).strip()


def list_gemini_models(api_key: str, timeout: int) -> list[dict]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models"
        f"?key={urllib.parse.quote(api_key)}"
    )
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini model-list HTTP {exc.code}: {body}") from exc
    return data.get("models", [])


def load_done(jsonl_path: Path) -> set[str]:
    done = set()
    if not jsonl_path.exists():
        return done
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                done.add(json.loads(line)["segment_id"])
            except Exception:
                continue
    return done


def normalize_record_categories(record: dict) -> None:
    for result in record.get("results", []):
        attr = result.get("attribute")
        cat_id = str(result.get("cat_id"))
        if attr in CATEGORIES and cat_id in CATEGORIES[attr]:
            category = CATEGORIES[attr][cat_id]
            result["cat_id"] = int(cat_id)
            result["category"] = category
            value = str(result.get("predicted_value", "")).strip()
            if not value or value == cat_id or value.startswith(f"{cat_id} "):
                result["predicted_value"] = category


def is_retryable_error(exc: Exception) -> bool:
    details = str(exc)
    return (
        isinstance(exc, json.JSONDecodeError)
        or "validation errors:" in details
        or any(code in details for code in ["HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504"])
    )


def is_quota_error(exc: Exception) -> bool:
    details = str(exc).lower()
    return "http 429" in details or "resource_exhausted" in details


def select_images_from_list(images: list[Path], dataset_root: Path, image_list: Path) -> list[Path]:
    with image_list.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "image_path" not in rows[0]:
        raise ValueError(f"Image list must contain an image_path column: {image_list}")

    available = {
        path.relative_to(dataset_root).as_posix().casefold(): path
        for path in images
    }
    requested = [row["image_path"].strip().replace("\\", "/") for row in rows]
    if len(requested) != len(set(path.casefold() for path in requested)):
        raise ValueError(f"Image list contains duplicate image_path values: {image_list}")
    missing = [path for path in requested if path.casefold() not in available]
    if missing:
        raise ValueError(f"Image list contains {len(missing)} paths absent from the dataset: {missing[:5]}")
    return [available[path.casefold()] for path in requested]


def write_wide_csv(jsonl_path: Path, csv_path: Path, model: str, method: str) -> None:
    fieldnames = ["segment_id", "folder_name", "image_name", "image_path", "method", "model"]
    for attr in ATTRIBUTES:
        slug = attr_slug(attr)
        fieldnames.extend([f"{slug}_predicted_value", f"{slug}_confidence", f"{slug}_cat_id", f"{slug}_evidence"])
    fieldnames.append("notes")

    with jsonl_path.open("r", encoding="utf-8") as src, csv_path.open(
        "w", newline="", encoding="utf-8"
    ) as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        for line in src:
            if not line.strip():
                continue
            record = json.loads(line)
            row = {
                "segment_id": record["segment_id"],
                "folder_name": record.get("folder_name"),
                "image_name": record.get("image_name"),
                "image_path": record["image_path"],
                "method": record.get("method", method),
                "model": model,
                "notes": "GT not used; visual-only zero-shot Gemini run.",
            }
            by_attr = {r["attribute"]: r for r in record["results"]}
            for attr in ATTRIBUTES:
                slug = attr_slug(attr)
                result = by_attr.get(attr, {})
                row[f"{slug}_predicted_value"] = result.get("predicted_value", result.get("category"))
                row[f"{slug}_confidence"] = result.get("confidence")
                row[f"{slug}_cat_id"] = result.get("cat_id")
                row[f"{slug}_evidence"] = result.get("evidence_summary", "")
            writer.writerow(row)


def load_records(jsonl_path: Path) -> list[dict]:
    records = []
    if not jsonl_path.exists():
        return records
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def write_irap_code_tables(records: list[dict], out_dir: Path) -> None:
    codes_csv = out_dir / "predicted_irap_codes.csv"
    detailed_csv = out_dir / "predicted_irap_codes_with_categories_confidence.csv"
    long_csv = out_dir / "predicted_irap_codes_long.csv"
    summary_path = out_dir / "prediction_export_summary.json"

    code_fields = ["segment_id", "folder_name", "image_name", "image_path", "model", "method"] + [
        f"pred_{slug}_cat_id" for _, slug in IRAP_EXPORT_ATTRIBUTES
    ]
    detail_fields = ["segment_id", "folder_name", "image_name", "image_path", "model", "method"]
    for _, slug in IRAP_EXPORT_ATTRIBUTES:
        detail_fields.extend([f"pred_{slug}_cat_id", f"pred_{slug}_category", f"pred_{slug}_confidence"])

    with codes_csv.open("w", newline="", encoding="utf-8") as f_codes, detailed_csv.open(
        "w", newline="", encoding="utf-8"
    ) as f_details, long_csv.open("w", newline="", encoding="utf-8") as f_long:
        code_writer = csv.DictWriter(f_codes, fieldnames=code_fields)
        detail_writer = csv.DictWriter(f_details, fieldnames=detail_fields)
        long_writer = csv.DictWriter(
            f_long,
            fieldnames=[
                "segment_id",
                "folder_name",
                "image_name",
                "image_path",
                "model",
                "method",
                "attribute",
                "predicted_cat_id",
                "predicted_category",
                "confidence",
                "evidence_summary",
                "measurement_note",
            ],
        )
        code_writer.writeheader()
        detail_writer.writeheader()
        long_writer.writeheader()

        for record in records:
            base = {
                "segment_id": record.get("segment_id"),
                "folder_name": record.get("folder_name"),
                "image_name": record.get("image_name"),
                "image_path": record.get("image_path"),
                "model": record.get("model"),
                "method": record.get("method"),
            }
            by_attr = {result.get("attribute"): result for result in record.get("results", [])}
            code_row = dict(base)
            detail_row = dict(base)
            for attribute, slug in IRAP_EXPORT_ATTRIBUTES:
                attr_result = by_attr.get(attribute, {})
                cat_id = attr_result.get("cat_id")
                category = attr_result.get("category")
                confidence = attr_result.get("confidence")
                code_row[f"pred_{slug}_cat_id"] = cat_id
                detail_row[f"pred_{slug}_cat_id"] = cat_id
                detail_row[f"pred_{slug}_category"] = category
                detail_row[f"pred_{slug}_confidence"] = confidence
                long_writer.writerow(
                    {
                        **base,
                        "attribute": attribute,
                        "predicted_cat_id": cat_id,
                        "predicted_category": category,
                        "confidence": confidence,
                        "evidence_summary": attr_result.get("evidence_summary", ""),
                        "measurement_note": attr_result.get("measurement_note"),
                    }
                )
            code_writer.writerow(code_row)
            detail_writer.writerow(detail_row)

    summary = {
        "ground_truth_used": False,
        "external_api_used": True,
        "record_count": len(records),
        "attribute_count": len(IRAP_EXPORT_ATTRIBUTES),
        "wide_codes_csv": str(codes_csv),
        "wide_detailed_csv": str(detailed_csv),
        "long_csv": str(long_csv),
        "compare_script_compatible": "scripts/compare_zero_shot_predictions_to_gt.py",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_progress_files(
    jsonl_path: Path, out_dir: Path, manifest: dict, model: str, method: str
) -> None:
    records = load_records(jsonl_path)
    save_results(out_dir / "results.json", records, manifest)
    write_wide_csv(jsonl_path, out_dir / "zero_shot_17_attribute_wide.csv", model, method)
    write_irap_code_tables(records, out_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="Dataset")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--env-file", default=".venv/.env")
    parser.add_argument("--image-list", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--stop-on-quota", action="store_true")
    args = parser.parse_args()

    load_env_file(Path(args.env_file))

    dataset_root = Path(args.dataset_root).resolve()
    out_dir = Path(args.out_dir or Path("artifacts") / args.run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    images = list_images(dataset_root)
    image_list_path = Path(args.image_list).resolve() if args.image_list else None
    if image_list_path:
        images = select_images_from_list(images, dataset_root, image_list_path)
    if args.limit:
        images = images[: args.limit]

    method = method_for_model(args.model)

    manifest_path = out_dir / "manifest.json"
    manifest = {
        "run_id": args.run_id,
        "method": method,
        "model": args.model,
        "created_date": datetime.now().isoformat(timespec="seconds"),
        "dataset_root": str(dataset_root),
        "ground_truth_used": False,
        "ground_truth_exclusion": [
            "GroundTruth.csv",
            "images-labeling-coding.xlsx",
            "any file containing existing manual labels",
        ],
        "image_count": len(images),
        "image_identifier_list": str(image_list_path) if image_list_path else None,
        "image_identifier_list_sha256": (
            hashlib.sha256(image_list_path.read_bytes()).hexdigest() if image_list_path else None
        ),
        "attributes": ATTRIBUTES,
        "images": [str(p.relative_to(dataset_root).as_posix()) for p in images],
        "prompt_version": PROMPT_VERSION,
        "prompt_file": str(PROMPT_PATH),
        "prompt_sha256": prompt_sha256(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Run ID: {args.run_id}")
    print(f"Model: {args.model}")
    print(f"Images selected: {len(images)}")
    print(f"Manifest: {manifest_path}")

    if args.dry_run:
        print("Dry run complete. No Gemini requests sent.")
        return 0

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set in environment or .venv/.env.")
        return 2

    if args.list_models:
        models = list_gemini_models(api_key, args.timeout)
        for model in models:
            methods = ",".join(model.get("supportedGenerationMethods", []))
            print(f"{model.get('name')}\t{model.get('displayName')}\t{methods}")
        return 0

    jsonl_path = out_dir / "zero_shot_17_attribute_results.jsonl"
    error_path = out_dir / "errors.jsonl"
    raw_dir = out_dir / "raw_responses"
    raw_dir.mkdir(exist_ok=True)
    done = set() if args.no_resume else load_done(jsonl_path)

    with jsonl_path.open("a", encoding="utf-8") as ok, error_path.open(
        "a", encoding="utf-8"
    ) as err:
        for idx, image_path in enumerate(images, start=1):
            segment_id = image_id(image_path, dataset_root)
            if segment_id in done:
                print(f"[{idx}/{len(images)}] skip existing {segment_id}", flush=True)
                continue
            print(f"[{idx}/{len(images)}] coding {segment_id}", flush=True)
            try:
                text = call_gemini(
                    build_common_prompt(image_path, dataset_root),
                    encode_image(image_path),
                    api_key,
                    args.timeout,
                    args.model,
                )
                (raw_dir / f"{segment_id}.txt").write_text(text, encoding="utf-8")
                record = parse_json_object(text)
                record["segment_id"] = segment_id
                record["folder_name"] = folder_name(image_path, dataset_root)
                record["image_name"] = image_path.name
                record["image_path"] = image_path.relative_to(dataset_root).as_posix()
                record["method"] = method
                record["model"] = args.model
                record["ground_truth_used"] = False
                normalize_record_categories(record)
                validation_errors = validate_record(record)
                if validation_errors:
                    raise ValueError(f"validation errors: {validation_errors}")
                record["validation_errors"] = validation_errors
                ok.write(json.dumps(record, ensure_ascii=False) + "\n")
                ok.flush()
                write_progress_files(jsonl_path, out_dir, manifest, args.model, method)
            except Exception as exc:
                last_exc = exc
                recovered = False
                for retry in range(1, args.max_retries + 1):
                    if not is_retryable_error(last_exc):
                        break
                    if args.stop_on_quota and is_quota_error(last_exc):
                        break
                    delay = min(120, 5 * (2 ** (retry - 1)))
                    print(f"  transient error; retry {retry}/{args.max_retries} after {delay}s: {type(last_exc).__name__}", flush=True)
                    time.sleep(delay)
                    try:
                        text = call_gemini(
                            build_common_prompt(image_path, dataset_root),
                            encode_image(image_path),
                            api_key,
                            args.timeout,
                            args.model,
                        )
                        (raw_dir / f"{segment_id}.txt").write_text(text, encoding="utf-8")
                        record = parse_json_object(text)
                        record["segment_id"] = segment_id
                        record["folder_name"] = folder_name(image_path, dataset_root)
                        record["image_name"] = image_path.name
                        record["image_path"] = image_path.relative_to(dataset_root).as_posix()
                        record["method"] = method
                        record["model"] = args.model
                        record["ground_truth_used"] = False
                        normalize_record_categories(record)
                        validation_errors = validate_record(record)
                        if validation_errors:
                            raise ValueError(f"validation errors: {validation_errors}")
                        record["validation_errors"] = validation_errors
                        ok.write(json.dumps(record, ensure_ascii=False) + "\n")
                        ok.flush()
                        write_progress_files(jsonl_path, out_dir, manifest, args.model, method)
                        recovered = True
                        break
                    except Exception as retry_exc:
                        last_exc = retry_exc
                if not recovered:
                    err.write(
                        json.dumps(
                            {
                                "segment_id": segment_id,
                                "image_path": image_path.relative_to(dataset_root).as_posix(),
                                "error": type(last_exc).__name__,
                                "details": str(last_exc),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    err.flush()
                    print(f"  ERROR: {type(last_exc).__name__}: {last_exc}", flush=True)
                    if args.stop_on_quota and is_quota_error(last_exc):
                        print("Quota limit detected; stopping cleanly for a later resume.", flush=True)
                        break
            time.sleep(args.sleep)

    write_progress_files(jsonl_path, out_dir, manifest, args.model, method)
    print(f"Results: {jsonl_path}")
    print(f"Wide CSV: {out_dir / 'zero_shot_17_attribute_wide.csv'}")
    print(f"Results JSON: {out_dir / 'results.json'}")
    print(f"Code CSV: {out_dir / 'predicted_irap_codes.csv'}")
    print(f"Errors: {error_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
