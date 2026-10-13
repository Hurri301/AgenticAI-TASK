#!/usr/bin/env python3
"""Blind Gemini Median Type verifier over the full prediction image set."""
from __future__ import annotations
import argparse, base64, csv, io, json, os, re, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from typing import Any
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/irap-carriageway-layout-coder"
MODEL = "gemini-3.5-flash-lite"

def load_env(path: Path) -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def rows(root: Path) -> list[dict[str, str]]:
    out=[]
    for p in sorted(root.glob("*/predicted_codes_all_attributes.csv")):
        with p.open(encoding="utf-8-sig", newline="") as f: out.extend(csv.DictReader(f))
    return sorted(out, key=lambda r:(r["folder_name"], int(float(r["frame_id"]))))

def enc(im: Image.Image) -> str:
    im=im.convert("RGB"); im.thumbnail((1100,700)); b=io.BytesIO(); im.save(b,"JPEG",quality=80); return base64.b64encode(b.getvalue()).decode()

def crop(im: Image.Image, frac: float) -> Image.Image:
    return im.crop((0,0,max(1,round(im.width*frac)),im.height))

def call(model: str, key: str, prompt: str, ims: list[Image.Image], timeout: int) -> str:
    parts=[{"text":prompt}]+[{"inline_data":{"mime_type":"image/jpeg","data":enc(i)}} for i in ims]
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model,safe='')}:generateContent?key={urllib.parse.quote(key)}"
    req=urllib.request.Request(url,data=json.dumps({"contents":[{"role":"user","parts":parts}],"generationConfig":{"response_mime_type":"application/json","temperature":0,"maxOutputTokens":1200}}).encode(),headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as response:
        body=json.loads(response.read().decode()); return "\n".join(p.get("text","") for p in body["candidates"][0]["content"]["parts"])

def parse(text: str) -> dict[str,Any]:
    text=re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()); a,b=text.find("{"),text.rfind("}"); return json.loads(text[a:b+1])

def sanitized_error(error: Exception, key: str) -> str:
    text = str(error)
    for secret in (key, urllib.parse.quote(key, safe="")):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return re.sub(r"(?i)([?&]key=)[^&\s]+", r"\1[REDACTED]", text)


def resolved(record: dict[str, Any]) -> bool:
    return bool(record.get("pred_code")) and not record.get("review_required") and not record.get("error")


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--predictions-root",default="artifacts/final_delivery_2026-07-01/predictions_final"); ap.add_argument("--outdir",required=True); ap.add_argument("--model",default=MODEL); ap.add_argument("--sleep",type=float,default=1.5); ap.add_argument("--max-retries",type=int,default=5); ap.add_argument("--folder-name", default=None); ap.add_argument("--limit", type=int, default=None); args=ap.parse_args()
    if args.limit is not None and args.limit < 0: ap.error("--limit must be nonnegative")
    if args.max_retries < 1: ap.error("--max-retries must be positive")
    load_env(ROOT/".venv/.env"); key=os.environ.get("GEMINI_API_KEY","").strip()
    if not key: raise RuntimeError("GEMINI_API_KEY is missing")
    source=rows(ROOT/args.predictions_root); out=ROOT/args.outdir; out.mkdir(parents=True,exist_ok=True); trace=out/"median_vlm_trace.jsonl"; done={}
    if trace.exists():
        for line in trace.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r=json.loads(line); k=(r["folder_name"],int(r["frame_id"]));
                if k not in done or not resolved(done[k]): done[k]=r
    prompt=(SKILL/"references/median-vlm-prompt.md").read_text(encoding="utf-8")
    grouped={}
    for r in source:
        if args.folder_name is None or r["folder_name"] == args.folder_name:
            grouped.setdefault(r["folder_name"],[]).append(r)
    attempted=0; stop_reason=None
    with trace.open("a",encoding="utf-8") as h:
        for folder, group in grouped.items():
            if stop_reason: break
            for i,row in enumerate(group):
                k=(folder,int(float(row["frame_id"])))
                if k in done and resolved(done[k]): continue
                if args.limit is not None and attempted >= args.limit: break
                attempted += 1
                paths=[ROOT/row["image_path"],ROOT/group[max(0,i-1)]["image_path"],ROOT/group[min(len(group)-1,i+1)]["image_path"]]
                ims=[]
                for j,p in enumerate(paths):
                    with Image.open(p) as im: ims.append(im.convert("RGB") if j==0 else crop(im.convert("RGB"),.55))
                raw={}; err=""; ok=False
                for attempt in range(1,args.max_retries+1):
                    try:
                        raw=parse(call(args.model,key,prompt+f"\nTarget folder: {folder}\nTarget frame: {k[1]}",ims,180)); code=int(raw.get("cat_id"));
                        if code not in range(1,16): raise ValueError("cat_id outside 1..15")
                        rec={"folder_name":folder,"frame_id":k[1],"image_path":row["image_path"],"pred_code":code,"confidence":raw.get("confidence",0),"review_required":bool(raw.get("review_required",False)),"vlm_output":raw,"attempts":attempt};
                        if rec["review_required"]: raise ValueError("review_required=true")
                        ok=True; break
                    except Exception as e:
                        err=sanitized_error(e,key)
                        if isinstance(e, urllib.error.HTTPError) and e.code in (429,401,403):
                            stop_reason=f"http_{e.code}"; break
                        if attempt < args.max_retries: time.sleep(min(60,10*attempt))
                if not ok: rec={"folder_name":folder,"frame_id":k[1],"image_path":row["image_path"],"pred_code":"","confidence":raw.get("confidence",0),"review_required":True,"error":err,"vlm_output":raw}
                rec["status"]="resolved" if ok else ("review_required" if raw.get("review_required") else "unresolved")
                done[k]=rec; h.write(json.dumps(rec)+"\n"); h.flush()
                if stop_reason: break
                time.sleep(args.sleep)
    with (out/"median_type_predictions.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["folder_name","frame_id","image_path","pred_code","confidence","review_required","status"]); w.writeheader();
        for k in sorted(done):
            record = done[k]
            exported = {x:record.get(x,"") for x in w.fieldnames}
            exported["status"] = record.get("status") or ("resolved" if resolved(record) else ("review_required" if record.get("vlm_output", {}).get("review_required") else "unresolved"))
            w.writerow(exported)
    summary={"rows":len(done),"attempted":attempted,"resolved":sum(resolved(r) for r in done.values()),"review_required":sum(r.get("status")=="review_required" for r in done.values()),"unresolved":sum(not resolved(r) and r.get("status")!="review_required" for r in done.values()),"stop_reason":stop_reason}
    (out/"run_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary))
    return 1 if stop_reason else 0
if __name__ == "__main__": raise SystemExit(main())
