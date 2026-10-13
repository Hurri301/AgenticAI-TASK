#!/usr/bin/env python
"""Shared frozen prompt loader for zero-shot iRAP model comparisons."""

from __future__ import annotations

import hashlib
from pathlib import Path


PROMPT_VERSION = "zero_shot_irap_17_attributes_updated_skills_v2"
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "zero_shot_irap_17_attributes_updated_skills_v2.md"


def prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def prompt_sha256() -> str:
    return hashlib.sha256(prompt_text().encode("utf-8")).hexdigest()


def build_common_prompt(image_path: Path, dataset_root: Path) -> str:
    rel_path = image_path.relative_to(dataset_root).as_posix()
    return prompt_text().replace("{image_path}", rel_path)
