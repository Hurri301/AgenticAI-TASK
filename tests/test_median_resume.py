import csv
import importlib.util
import json
import sys
import urllib.error
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def runner(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/run_median_type_gemini.py"
    spec = importlib.util.spec_from_file_location("median_resume", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "SKILL", tmp_path)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setenv("GEMINI_API_KEY", "private-secret")
    (tmp_path / "references").mkdir()
    (tmp_path / "references/median-vlm-prompt.md").write_text("Test prompt")
    Image.new("RGB", (8, 8)).save(tmp_path / "image.jpg")
    monkeypatch.setattr(module, "rows", lambda _: [
        {"folder_name": folder, "frame_id": str(frame), "image_path": "image.jpg"}
        for folder, frame in [("01_N3", 1), ("01_N3", 2), ("02_A23", 1)]
    ])
    monkeypatch.setattr(sys, "argv", ["run", "--outdir", "out", "--folder-name", "01_N3"])
    return module, tmp_path


def test_resume_preserves_success_and_scopes_folder(runner, monkeypatch):
    module, root = runner
    (root / "out").mkdir()
    success = {"folder_name": "01_N3", "frame_id": 1, "pred_code": 3, "review_required": False}
    failure = {**success, "pred_code": "", "review_required": True}
    trace = root / "out/median_vlm_trace.jsonl"
    trace.write_text(json.dumps(success) + "\n" + json.dumps(failure) + "\n")
    prompts = []
    def fake_call(model, key, prompt, ims, timeout):
        prompts.append(prompt)
        return '{"cat_id": 4}'
    monkeypatch.setattr(module, "call", fake_call)
    assert module.main() == 0
    assert len(prompts) == 1 and "Target frame: 2" in prompts[0]
    with (root / "out/median_type_predictions.csv").open() as handle:
        records = list(csv.DictReader(handle))
    assert [(r["folder_name"], r["pred_code"]) for r in records] == [("01_N3", "3"), ("01_N3", "4")]


@pytest.mark.parametrize("status", [429, 401, 403])
def test_http_stop_exports_partial_and_redacts_secret(runner, monkeypatch, status):
    module, root = runner
    calls = []
    def fake_call(*args):
        calls.append(args)
        if len(calls) == 1:
            return '{"cat_id": 3}'
        raise urllib.error.HTTPError("https://test?key=private-secret", status, "key=private-secret", {}, None)
    monkeypatch.setattr(module, "call", fake_call)
    assert module.main() == 1
    assert len(calls) == 2
    summary = json.loads((root / "out/run_summary.json").read_text())
    assert summary["resolved"] == 1 and summary["unresolved"] == 1
    assert summary["stop_reason"] == f"http_{status}"
    assert (root / "out/median_type_predictions.csv").exists()
    assert "private-secret" not in (root / "out/median_vlm_trace.jsonl").read_text()


def test_limit_bounds_missing_frame_attempts(runner, monkeypatch):
    module, root = runner
    monkeypatch.setattr(sys, "argv", ["run", "--outdir", "out", "--limit", "1"])
    calls = []
    def fake_call(*args):
        calls.append(args)
        return '{"cat_id": 3}'
    monkeypatch.setattr(module, "call", fake_call)
    assert module.main() == 0
    assert len(calls) == 1
