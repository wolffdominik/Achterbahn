import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. ABSOLUTER PFAD-FIX & MANUELLER IMPORT ---
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

def manual_import(name, folder):
    """Spezielle Funktion, um Module auf Render sicher zu laden."""
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

# Module laden (Wichtig für Linux/Render)
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

# --- 3. KLASSEN-ZUWEISUNG (Mapping main.py -> Track.py) ---
if track_mod:
    # Wir weisen die kleingeschriebenen Klassen aus Track.py 
    # den CamelCase-Variablen in main.py zu.
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

# --- 4. WEB-SERVER FÜR RENDER (Health Check) ---
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

# --- 6. KONSTANTEN & FABRIKEN (Erst hier, wenn Klassen zugewiesen sind) ---
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
        self.train =
