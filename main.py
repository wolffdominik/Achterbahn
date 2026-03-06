import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. ABSOLUTER PFAD-FIX ---
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

def manual_import(name, folder):
    path = current_dir / folder / f"{name}.py"
    if path.exists():
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        print(f"ERFOLG: {name} aus {folder} geladen.")
        return module
    print(f"FEHLER: Datei nicht gefunden: {path}")
    return None

# Module laden
track_mod = manual_import("Track", "track")
ui_mod = manual_import("ui", "ui")
wagon_mod = manual_import("wagon", "wagon")
commands_mod = manual_import("commands", "track")

# --- 2. PANDA3D HEADLESS CONFIG ---
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none\naudio-library-name null')

from flask import Flask
from ursina import *
from ursina.prefabs.editor_camera import EditorCamera

# --- 3. KLASSEN-ZUWEISUNG (Exakt abgestimmt auf deine Track.py!) ---
if track_mod:
    # WICHTIG: Kleingeschriebene Endungen wie in deiner Track.py (z.B. Straightsegment)
    StraightSegment = track_mod.Straightsegment
    ShortStraightSegment = track_mod.Shortstraightsegment
    CurveSegment = track_mod.Curvesegment
    HillUpSegment = track_mod.Hillupsegment
    HillDownSegment = track_mod.Hilldownsegment
    LoopSegment = track_mod.Loopsegment
    CorkscrewSegment = track_mod.Corkscrewsegment
    TrackManager = track_mod.Trackmanager
    set_rotation = getattr(track_mod, 'set_rotation', None)

if ui_mod:
    ColorPicker = ui_mod.ColorPicker
    SegmentPalette = ui_mod.SegmentPalette
    TrackControls = ui_mod.TrackControls

if wagon_mod:
    Train = wagon_mod.Train

CommandManager = commands_mod.CommandManager if commands_mod else None

# --- 4. WEB-SERVER FÜR RENDER ---
web_app = Flask(__name__)
@web_app.route('/')
def health_check():
    return "Achterbahn-Server läuft!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_web_server, daemon=True).start()

# --- 5. INITIALISIERUNG ---
is_render = 'RENDER' in os.environ
app = Ursina(headless=is_render, title="Achterbahn Designer")

# --- 6. KONSTANTEN & FABRIKEN (Erst hier, wenn Klassen geladen sind!) ---
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

# --- 7. GAME LOGIC ---
def create_ground():
    return Entity(model="plane", scale=(1200, 100, 1200), color=color.lime * 0.45)

def setup_lighting():
    sun = DirectionalLight()
    sun.look_at(Vec3(1, -2, 1))
    AmbientLight(color=color.rgba(200, 200, 220, 0.3))

class GameState:
    def __init__(self):
        self.manager = TrackManager()
        self.segment_idx = 0
        self.color_key = "schwarz"
        self.running = False
        self._preview = None
        
        self.palette = SegmentPalette([n for n, _ in SEGMENT_FACTORIES], self.set_segment_type)
        self.color_ui = ColorPicker(TRACK_COLORS, self.set_color)
        self.controls = TrackControls(self._on_toggle)
        
        self._hud = Text(text="", position=(-0.85, -0.38), scale=1.1, parent=camera.ui)
        self.train = Train(self.manager)
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
        if running: self.train.start()
        else: self.train.stop()

    def place(self):
        c = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        self.manager.add_segment(factory(c))
        self._refresh_preview(); self._update_hud()

    def undo(self):
        self.manager.remove_last()
        self._refresh_preview(); self._update_hud()

    def clear_track(self):
        self.train.stop(); self.running = False; self.controls.toggle()
        self.manager.clear(); self._refresh_preview(); self._update_hud()

    def next_type(self):
        self.segment_idx = (self.segment_idx + 1) % len(SEGMENT_FACTORIES)
        self.palette.select(self.segment_idx); self._refresh_preview(); self._update_hud()

    def next_color(self):
        idx = COLOR_KEYS.index(self.color_key)
        self.color_key = COLOR_KEYS[(idx + 1) % len(COLOR_KEYS)]
        self.color_ui.select(self.color_key); self._refresh_preview(); self._update_hud()

    def _refresh_preview(self):
        if self._preview: destroy(self._preview)
        c = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        preview_seg = factory(color.rgba(c.r, c.g, c.b, 0.35))
        self._preview = preview_seg.spawn()
        # Fix: Name in deiner Track.py ist 'apply_exit_transformation'
        if hasattr(self.manager, 'apply_exit_transformation'):
            self.manager.apply_exit_transformation(self._preview)

    def _update_hud(self):
        self._hud.text = f"Teile: {len(self.manager.segments)}\n[RÜCKTASTE] Undo\n[C] Clear\n[ENTER] Start"

# --- 8. EVENTS ---
state = None
def update():
    if state and state.running:
        state.train.update(state.controls.speed)

def input(key):
    if not state: return
    if key == "space": state.place()
    elif key == "backspace": state.undo()
    elif key == "tab": state.next_type()
    elif key == "q": state.next_color()
    elif key == "c": state.clear_track()
    elif key == "enter": state.controls.toggle()

if __name__ == "__main__":
    setup_lighting(); create_ground(); Sky()
    state = GameState()
    EditorCamera()
    app.run()
