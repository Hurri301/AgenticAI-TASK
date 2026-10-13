#!/usr/bin/env python3
"""
Extract searchable text snippets from the iRAP PDF manual using stdlib only.

This script targets common text operators in PDF content streams (Tj/TJ) and
is intended for focused keyword lookup, not full-fidelity document conversion.
"""

from __future__ import annotations

import argparse
import json
import re
import zlib
from pathlib import Path


def _decode_pdf_string(value: str) -> str:
    return (
        value.replace(r"\n", " ")
        .replace(r"\r", " ")
        .replace(r"\t", " ")
        .replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
    )


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, dict]:
    data = pdf_path.read_bytes()

    stream_count = 0
    decompressed_count = 0
    fragments: list[str] = []

    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        stream_count += 1
        raw_stream = match.group(1)

        decoded: bytes | None = None
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS, 15 + 32):
            try:
                decoded = zlib.decompress(raw_stream, wbits)
                break
            except Exception:
                continue

        if decoded is None:
            continue

        decompressed_count += 1
        text = decoded.decode("latin1", errors="ignore")

        for m in re.finditer(r"\(([^)]{2,280})\)\s*Tj", text, re.S):
            fragments.append(_decode_pdf_string(m.group(1)))

        for m in re.finditer(r"\[(.*?)\]\s*TJ", text, re.S):
            tj_payload = m.group(1)
            for s in re.findall(r"\(([^)]{2,280})\)", tj_payload, re.S):
                fragments.append(_decode_pdf_string(s))

    merged = re.sub(r"\s+", " ", " ".join(fragments)).strip()
    stats = {
        "pdf_path": str(pdf_path),
        "stream_count": stream_count,
        "decompressed_streams": decompressed_count,
        "fragment_count": len(fragments),
        "text_length": len(merged),
    }
    return merged, stats


def find_hits(text: str, query: str, max_hits: int, context_chars: int) -> list[dict]:
    hits: list[dict] = []
    lower = text.lower()
    needle = query.lower()
    start = 0

    while len(hits) < max_hits:
        idx = lower.find(needle, start)
        if idx < 0:
            break
        left = max(0, idx - context_chars)
        right = min(len(text), idx + len(query) + context_chars)
        hits.append(
            {
                "query": query,
                "index": idx,
                "snippet": text[left:right],
            }
        )
        start = idx + len(query)

    return hits


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lookup keyword snippets from iRAP Coding Manual PDF."
    )
    parser.add_argument(
        "--pdf",
        default=(
            Path(__file__).resolve().parent.parent
            / "references"
            / "iRAP_Coding_Manual_Drive_on_Right.pdf"
        ),
        type=Path,
        help="Path to the iRAP PDF file.",
    )
    parser.add_argument(
        "--query",
        action="append",
        required=True,
        help="Query term or phrase. Repeat for multiple queries.",
    )
    parser.add_argument("--max-hits", type=int, default=3, help="Max hits per query.")
    parser.add_argument(
        "--context-chars",
        type=int,
        default=180,
        help="Characters before and after each hit.",
    )
    parser.add_argument("--out-json", type=Path, default=None, help="Optional output path.")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")

    text, stats = extract_text_from_pdf(args.pdf)

    all_hits: list[dict] = []
    for q in args.query:
        all_hits.extend(
            find_hits(
                text=text,
                query=q,
                max_hits=max(1, args.max_hits),
                context_chars=max(40, args.context_chars),
            )
        )

    result = {
        "source": "irap_pdf_lookup",
        "stats": stats,
        "queries": args.query,
        "hits": all_hits,
    }

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(payload, encoding="utf-8")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
