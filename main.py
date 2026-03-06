import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. PFAD-FIX & INTELLIGENTER IMPORT ---
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

def manual_import(name, folder):
    """Sucht nach Dateien (Groß/Klein) und lädt sie direkt."""
    # Wir prüfen Track.py, track.py, UI.py, ui.py etc.
    possible_filenames = [name, name.capitalize(), name.lower()]
    for filename in possible_filenames:
        path = current_dir / folder / f"{filename}.py"
        if path.exists():
            spec = importlib.util.spec_from_file_location(name, str(path))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            print(f"ERFOLG: {filename} aus {folder} geladen.")
            return module
    print(f"FEHLER: Modul {name} in /{folder} nicht gefunden!")
    return None

# Module laden
track_mod = manual_import("Track", "track")
ui_mod = manual_import("ui", "ui")
wagon_mod = manual_import("wagon", "wagon")
commands_mod = manual_import("commands", "track")

# --- 2. PANDA3D / URSINA HEADLESS FORCE (Muss vor Ursina kommen!) ---
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'load-display none')
loadPrcFileData('', 'audio-library-name null')

from flask import Flask
from ursina import *
from ursina.prefabs.editor_camera import EditorCamera

# --- 3. KLASSEN-ZUWEISUNG ---
if track_mod:
    StraightSegment = getattr(track_mod, 'Straightsegment', getattr(track_mod, 'StraightSegment', None))
    ShortStraightSegment = getattr(track_mod, 'Shortstraightsegment', getattr(track_mod, 'ShortStraightSegment', None))
    CurveSegment = getattr(track_mod, 'Curvesegment', getattr(track_mod, 'CurveSegment', None))
    HillUpSegment = getattr(track_mod, 'Hillupsegment', getattr(track_mod, 'HillUpSegment', None))
    HillDownSegment = getattr(track_mod, 'Hilldownsegment', getattr(track_mod, 'HillDownSegment', None))
    LoopSegment = getattr(track_mod, 'Loopsegment', getattr(track_mod, 'LoopSegment', None))
    CorkscrewSegment = getattr(track_mod, 'Corkscrewsegment', getattr(track_mod, 'CorkscrewSegment', None))
    TrackManager = getattr(track_mod, 'Trackmanager', getattr(track_mod, 'TrackManager', None))

if ui_mod:
    ColorPicker = getattr(ui_mod, 'ColorPicker', None)
    SegmentPalette = getattr(ui_mod, 'SegmentPalette', None)
    TrackControls = getattr(ui_mod, 'TrackControls', None)

if wagon_mod:
    Train = getattr(wagon_mod, 'Train', None)

CommandManager = getattr(commands_mod, 'CommandManager', None) if commands_mod else None

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
is_render = 'RENDER' in os.environ or os.environ.get('PORT') is not None
if is_render:
    from ursina import application
    application.window_type = 'none'

app = Ursina(headless=is_render)

# --- 6. KONSTANTEN & FABRIKEN ---
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
    ("Schraube",     lambda c: CorkscrewSegment(c
