# Reproducibility Guide

## Scope

The experiment evaluates multimodal agentic coding of 17 iRAP road attributes
from 468 panoramic observations. The repository provides the deterministic
projection utilities, attribute rules, prompts, workflow skills, evaluation
scripts and tests. It does not redistribute the raw panoramic imagery,
mobile-LiDAR point clouds, trajectories or private API credentials.

## Environment

Use Python 3.9 or newer. Install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install the additional dependencies required by the selected experiment
script, then keep credentials in environment variables or a local `.env` file
that is never committed. At minimum, scripts using Gemini require
`GEMINI_API_KEY`; scripts using other hosted models require the credentials
specified by their command-line help.

## Expected local inputs

Place private inputs outside the public repository when possible. The
projection examples expect calibration, trajectory, panorama and point-cloud
files under the paths documented by each script. Do not commit those files.
Use anonymized manifests containing filenames, dimensions, hashes and metadata
when sharing an experiment configuration.

## Validation

Run the deterministic package tests before running the full experiment:

```bash
python -m pytest tests -q
```

The projection examples are:

```bash
python scripts/bbox_to_points.py --help
python scripts/points_to_bbox.py --help
```

## Experiment organization

- `src/mm_link/`: reusable image/LiDAR projection and geometry code.
- `.agents/skills/`: attribute-specific workflow instructions and tool routers.
- `prompts/`: frozen and updated prompt specifications.
- `scripts/`: selected experiment and evaluation entry points.
- `tests/`: regression and projection tests.
- `data/`: small public-safe examples and metadata only.
- `artifacts/`: generated outputs; ignored by Git.

## Reproducibility record

For each run, record the commit identifier, Python and package versions,
model/checkpoint identifiers, prompt version, confidence thresholds, input
manifest hash, inference date, hardware, API model versions, output path and
evaluation command. Do not publish API keys or raw model responses containing
restricted data.

## Results

Generated predictions and metrics should be written to a dated subdirectory of
`artifacts/`. Keep one small machine-readable manifest and the final aggregate
metrics for each reported configuration. Large raw responses and image
overlays should remain local or be published separately when permitted.
