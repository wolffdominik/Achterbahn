import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. PFAD-SYSTEM ---
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def safe_import(module_name, file_name):
    """Sucht gezielt nach deiner Datei im Projektordner, ignoriert System-Libraries."""
    print(f"Suche nach {file_name}...")
    for path in project_root.rglob(file_name):
        if ".venv" in str(path) or "__pycache__" in str(path) or "site-packages" in str(path):
            continue
        print(f"Gefunden: {path}. Lade als {module_name}...")
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    return None

# --- 2. MANUELLES LADEN (Vermeidet Namenskonflikte) ---
track_mod = safe_import("custom_track", "Track.py")
ui_mod    = safe_import("custom_ui", "ui.py")
wagon_mod = safe_import("custom_wagon", "wagon.py")
cmd_mod   = safe_import("custom_commands", "commands.py")

# --- 3. PANDA3D GRAFIK-KILLER ---
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none\nload-display none\naudio-library-name null')

# --- 4. KLASSEN-BINDUNG ---
def get_cls(mod, attr_name):
    if not mod: return None
    for attr in dir(mod):
        if attr.lower() == attr_name.lower():
            return getattr(mod, attr)
    return None

StraightSegment = get_cls(track_mod, 'Straightsegment')
ShortStraightSegment = get_cls(track_mod, 'Shortstraightsegment')
CurveSegment = get_cls(track_mod, 'Curvesegment')
HillUpSegment = get_cls(track_mod, 'Hillupsegment')
HillDownSegment = get_cls(track_mod, 'Hilldownsegment')
LoopSegment = get_cls(track_mod, 'Loopsegment')
CorkscrewSegment = get_cls(track_mod, 'Corkscrewsegment')
TrackManager = get_cls(track_mod, 'Trackmanager')

ColorPicker = get_cls(ui_mod, 'ColorPicker')
SegmentPalette = get_cls(ui_mod, 'SegmentPalette')
TrackControls = get_cls(ui_mod, 'TrackControls')
Train = get_cls(wagon_mod, 'Train')

# --- 5. URSINA & FLASK INITIALISIERUNG ---
from flask import Flask
import ursina
from ursina import Ursina, Entity, color, Vec3, Sky, camera, Text, destroy, DirectionalLight, AmbientLight
from ursina.prefabs.editor_camera import EditorCamera

web_app = Flask(__name__)
@web_app.route('/')
def health_check(): return "Achterbahn-Server läuft!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

is_render = 'RENDER' in os.environ
if is_render:
    ursina.application.window_type = 'none'

app = Ursina(headless=is_render)

# --- 6. GAME LOGIC KONFIGURATION ---
TRACK_COLORS = {
    "grau": color.gray, "blau": color.blue, "rot": color.red,
    "gelb": color.yellow, "lila": color.violet, "schwarz": color.black,
}
COLOR_KEYS = list(TRACK_COLORS.keys())

SEGMENT_FACTORIES = [
    ("Gerade",       lambda c: StraightSegment(c)),
    ("Gerade kurz",  lambda c: ShortStraightSegment(c)),
    ("Hügel rauf",   lambda c: HillUpSegment(c)),
    ("Hügel runter", lambda c: HillDownSegment(c)),
    ("Kurve 90 R",   lambda c: CurveSegment(90, "right", c)),
    ("Kurve 45 R",   lambda c: CurveSegment(45, "right", c)),
    ("Kurve 90 L",   lambda c: CurveSegment(90, "left",  c)),
    ("Kurve 45 L",   lambda c: CurveSegment(45, "left",  c)),
    ("Looping",      lambda c: LoopSegment(c)),
    ("Schraube",     lambda c: CorkscrewSegment(c)),
]

class GameState:
    def __init__(self):
        self.manager = TrackManager() if TrackManager else None
        self.segment_idx = 0
        self.color_key = "schwarz"
        self.running = False
        self._preview = None
        
        # UI Setup
        if SegmentPalette:
            self.palette = SegmentPalette([n for n, _ in SEGMENT_FACTORIES], self.set_segment_type)
        if ColorPicker:
            self.color_ui = ColorPicker(TRACK_COLORS, self.set_color)
        if TrackControls:
            self.controls = TrackControls(self._on_toggle)
            
        self._hud = Text(text="", position=(-0.85, -0.38), scale=1.1, parent=camera.ui)
        self.train = Train(self.manager) if Train else None
        self._update_hud()
        self._refresh_preview()

    def set_segment_type(self, idx):
        self.segment_idx = idx
        self._refresh_preview(); self._update_hud()

    def set_color(self, key):
        self.color_key = key
        self._refresh_preview(); self._update_hud()

    def _on_toggle(self, running):
        self.running = running
        if self.train:
            if running: self.train.start()
            else: self.train.stop()

    def place(self):
        if not self.manager: return
        c = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        self.manager.add_segment(factory(c))
        self._refresh_preview(); self._update_hud()

    def undo(self):
        if self.manager: self.manager.remove_last()
        self._refresh_preview(); self._update_hud()

    def _refresh_preview(self):
        if self._preview: destroy(self._preview)
        if not StraightSegment: return
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        c = TRACK_COLORS[self.color_key]
        preview_seg = factory(color.rgba(c.r, c.g, c.b, 0.35))
        self._preview = preview_seg.spawn()
        if self.manager and hasattr(self.manager, 'apply_exit_transformation'):
            self.manager.apply_exit_transformation(self._preview)

    def _update_hud(self):
        count = len(self.manager.segments) if self.manager else 0
        self._hud.text = f"Teile: {count}\n[ENTER] Start/Stop"

# --- 7. START & EVENTS ---
state = None

def update():
    if state and state.running and state.train:
        # Falls TrackControls einen Speed-Slider hat
        speed = state.controls.speed if hasattr(state.controls, 'speed') else 1
        state.train.update(speed)

if __name__ == "__main__":
    DirectionalLight().look_at(Vec3(1, -2, 1))
    AmbientLight(color=color.rgba(200, 200, 220, 0.3))
    Sky()
    state = GameState()
    if not is_render:
        EditorCamera()
    app.run()
