import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. ABSOLUTER PFAD-FIX & MANUELLER IMPORT ---
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

def manual_import(name, folder):
    """Erzwingt das Laden eines Moduls aus einem Unterordner."""
    path = current_dir / folder / f"{name}.py"
    if path.exists():
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        print(f"Manually loaded {name} from {path}")
        return module
    print(f"ERROR: Could not find {path}")
    return None

# Kritische Module laden
track_mod = manual_import("Track", "track")
ui_mod = manual_import("ui", "ui")
wagon_mod = manual_import("wagon", "wagon")

# --- 2. PANDA3D HEADLESS CONFIG ---
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none\naudio-library-name null')

# --- 3. IMPORTS AUS DEN MODULEN ---
if track_mod:
    CorkscrewSegment = track_mod.CorkscrewSegment
    CurveSegment = track_mod.CurveSegment
    HillDownSegment = track_mod.HillDownSegment
    HillUpSegment = track_mod.HillUpSegment
    LoopSegment = track_mod.LoopSegment
    ShortStraightSegment = track_mod.ShortStraightSegment
    StraightSegment = track_mod.StraightSegment
    TrackManager = track_mod.TrackManager
    
# Falls track_manager.py eine separate Datei ist:
try:
    from track.track_manager import set_rotation
except ImportError:
    # Falls es in Track.py steckt:
    set_rotation = getattr(track_mod, 'set_rotation', None)

if ui_mod:
    ColorPicker = ui_mod.ColorPicker
    SegmentPalette = ui_mod.SegmentPalette
    TrackControls = ui_mod.TrackControls

if wagon_mod:
    Train = wagon_mod.Train

# Standard-Library & Framework Imports
from flask import Flask
from ursina import *
from ursina.prefabs.editor_camera import EditorCamera
from commands import CommandManager

# --- 4. WEB-SERVER FÜR RENDER (Health Check) ---
web_app = Flask(__name__)
@web_app.route('/')
def health_check():
    return "Achterbahn-Server läuft!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# --- 5. URSINA INITIALISIERUNG ---
is_render = 'RENDER' in os.environ
app = Ursina(headless=is_render, title="Achterbahn Designer")

# --- 6. KONSTANTEN & SZENEN-LOGIK ---
TRACK_COLORS: dict[str, color] = {
    "grau":    color.gray,
    "blau":    color.blue,
    "rot":     color.red,
    "gelb":    color.yellow,
    "lila":    color.violet,
    "schwarz": color.black,
}
DEFAULT_COLOR_KEY = "schwarz"
COLOR_KEYS = list(TRACK_COLORS.keys())

def create_ground() -> Entity:
    return Entity(model="plane", scale=(1200, 100, 1200), color=color.lime * 0.45)

def setup_lighting() -> None:
    sun = DirectionalLight()
    sun.look_at(Vec3(1, -2, 1))
    AmbientLight(color=color.rgba(200, 200, 220, 0.3))

SEGMENT_FACTORIES: list[tuple[str, object]] = [
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

# --- 7. GAMESTATE KLASSE ---
class GameState:
    def __init__(self) -> None:
        self.manager     = TrackManager()
        self.segment_idx = 0
        self.color_key   = DEFAULT_COLOR_KEY
        self.running     = False
        self._preview: Entity | None = None

        seg_names    = [name for name, _ in SEGMENT_FACTORIES]
        self.palette  = SegmentPalette(seg_names, self.set_segment_type)
        self.color_ui = ColorPicker(TRACK_COLORS, self.set_color)
        self.controls = TrackControls(self._on_toggle)

        self._hud = Text(text="", position=(-0.85, -0.38), scale=1.1, parent=camera.ui)
        self.train = Train(self.manager)
        self._update_hud()
        self._refresh_preview()

    def set_segment_type(self, idx: int):
        self.segment_idx = idx
        self._refresh_preview()
        self._update_hud()

    def set_color(self, key: str):
        self.color_key = key
        self._refresh_preview()
        self._update_hud()

    def _on_toggle(self, running: bool):
        self.running = running
        if running: self.train.start()
        else: self.train.stop()

    def place(self):
        c = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        self.manager.add_segment(factory(c))
        self._refresh_preview()
        self._update_hud()

    def undo(self):
        self.manager.remove_last()
        self._refresh_preview()
        self._update_hud()

    def clear_track(self):
        self.train.stop()
        self.running = False
        self.controls.toggle()
        self.manager.clear()
        self._refresh_preview()
        self._update_hud()

    def next_type(self):
        self.segment_idx = (self.segment_idx + 1) % len(SEGMENT_FACTORIES)
