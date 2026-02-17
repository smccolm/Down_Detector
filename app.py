
import os
import gradio as gr
from models import AppConfig, Profile
from storage import ensure_dirs, save_json, load_json
from utils import duration_to_seconds, normalize_rule_list, iso, now_local
from engine import run_tick
from ui import build_dashboard

BASE_DIR = os.path.join(os.path.dirname(__file__), "Logs")
ensure_dirs(BASE_DIR)

profiles_path = os.path.join(BASE_DIR, "profiles.json")
cfg_data = load_json(profiles_path, {"profiles": []})
cfg = AppConfig()

for p in cfg_data.get("profiles", []):
    cfg.profiles.append(Profile(**p))

def save_profiles():
    save_json(profiles_path, {"profiles": [p.__dict__ for p in cfg.profiles]})

def dashboard():
    return build_dashboard(cfg)

with gr.Blocks() as demo:
    gr.Markdown("## Uptime Monitor (Modular Refactor)")
    dash = gr.HTML(dashboard())
    refresh = gr.Button("Refresh")
    refresh.click(fn=dashboard, outputs=dash)

demo.launch()
