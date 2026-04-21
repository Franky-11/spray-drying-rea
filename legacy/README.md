# Legacy Archive

This directory contains archived code paths that are intentionally kept outside the active React/FastAPI application.

Contents:

- `streamlit_ui/`: previous Streamlit-based UI and process simulation workflow
- `python_core/`: legacy simulation, process simulation, and calibration modules
- `data/`: archived data files used only by legacy workflows
- `tests/`: tests covering the archived modules

These paths are not part of the active Docker image or active runtime requirements. To work with the archived tooling, install:

```bash
pip install -r requirements.txt -r requirements-dev.txt -r requirements-legacy.txt
```
