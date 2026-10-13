# Setup / Installation Needs

Updated: 2026-04-30

This file separates what likely needs installation from what needs a code/data decision.

## Ask User To Install Or Approve

These normal Python environment packages are now installed and verified:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest laspy scipy scikit-learn
```

Open3D is also now installed and verified:

```powershell
.\.venv\Scripts\python.exe -m pip install open3d
```

Verified versions on 2026-04-30:

- `pytest==9.0.3`
- `laspy==2.7.0`
- `scipy==1.17.1`
- `scikit-learn==1.8.0`
- `open3d==0.19.0`

For GroundingDINO image detection, the skill-native route is now mostly installed.

Route A - skill-native GroundingDINO:

```powershell
.\.venv\Scripts\python.exe -m pip install torchvision
```

Installed/verified on 2026-05-04:

- `torch==2.11.0+cpu`
- `torchvision==0.26.0+cpu`
- editable `groundingdino==0.1.0` from `<repository-root>\GroundingDINO`
- config exists at `GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py`

Still required:

- cache/download `bert-base-uncased` tokenizer/config/model weights for the GroundingDINO text encoder

Completed on 2026-05-04:

- `GroundingDINO/weights/groundingdino_swint_ogc.pth` exists, size 693,997,677 bytes

Route B - Hugging Face detector already partly supported by `detect_roadside_severity.py`:

- keep using installed `transformers`, `torch`, `opencv-python`, and `tqdm`
- download/cache `IDEA-Research/grounding-dino-base`
- download/cache `facebook/sam-vit-base` if SAM masks are needed

## Files To Provide Or Locate

- `images-labeling-coding.xlsx` at `<repository-root>\images-labeling-coding.xlsx`, or update `scripts/analyze_code_representativeness.py` to the real workbook path.

## Code Still Missing

The point-cloud skill currently points to scripts that are absent:

- `scripts/segment_road_cloud.py`
- `scripts/pointcloud/cluster_euclidean.py`
- `scripts/pointcloud/min_cluster_distance.py`
- `scripts/visualize_segmented_cloud.py`

These are not just packages; they need to be restored, implemented, or replaced in the router.

## After Installation Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```powershell
.\.venv\Scripts\python.exe -c "import pytest, laspy, scipy, sklearn; print('core validation packages OK')"
```

For Open3D if installed:

```powershell
.\.venv\Scripts\python.exe -c "import open3d; print('open3d OK')"
```

For skill-native GroundingDINO:

```powershell
.\.venv\Scripts\python.exe -c "import torch, torchvision, groundingdino; print('groundingdino stack OK')"
```
