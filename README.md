# Down Detector (Local Uptime Monitor)

A local Gradio app that checks configured URLs on a schedule and writes machine-readable JSONL logs.

## Setup (Windows 11)
1. Run `setup_venv.bat`
2. Run `launcher.bat`
3. Open `http://127.0.0.1:7860`

## Dependencies
Installed via `requirements.txt`:
- gradio
- requests

## Data and Logs
Runtime files are written next to the app:
- `.\Logs\profiles.json`
- `.\Logs\log_meta.json`
- `.\Logs\uptime_log_*.jsonl`
- `.\Logs\error.log`

`Logs\` and `.venv\` are ignored by git.
