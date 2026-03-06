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

# Manuelles Laden der Untermodule
track_mod = manual_import("Track", "track")
ui_mod = manual_import("ui", "ui")
wagon_mod = manual_import("wagon", "wagon")
commands_mod = manual_import("commands", "track") # Liegt im track-Ordner

# --- 2. PANDA3D / URSINA HEADLESS CONFIG ---
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none\naudio-library-name null')

# --- 3. KLASSEN-ZUWEISUNG (Exakt wie in deiner Track.py!) ---
if track_mod:
    # ACHTUNG: Kleinschreibung am Wortanfang innerhalb des Namens beachten!
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

if commands_mod:
    CommandManager = commands_mod.CommandManager
else:
    CommandManager = None

# Framework Imports
from flask import Flask
from ursina import *
from ursina.prefabs.editor_camera import EditorCamera

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
    ("Gerade",       lambda c
