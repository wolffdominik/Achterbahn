import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. PFAD-SYSTEM ---
current_path = Path(__file__).resolve().parent
project_root = current_path / "Achterbahn" if (current_path / "Achterbahn").exists() else current_path
sys.path.insert(0, str(project_root))

# --- 2. EXTREMER HEADLESS-FIX (MUSS VOR URSINA KOMMEN) ---
from panda3d.core import loadPrcFileData
# Wir sagen Panda3D, dass es gar kein Display-Modul laden soll
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'load-display none') 
loadPrcFileData('', 'audio-library-name null')
loadPrcFileData('', 'aux-display none')

# Wir verhindern, dass Ursina versucht, ein Fenster zu erzwingen
import ursina
from ursina import application
is_render = 'RENDER' in os.environ or os.environ.get('PORT') is not None
if is_render:
    application.window_type = 'none'

# Jetzt erst die restlichen Ursina-Klassen laden
from ursina import Ursina, Entity, color, Vec3, Sky, camera, Text, destroy, DirectionalLight, AmbientLight
from ursina.prefabs.editor_camera import EditorCamera
from flask import Flask

# --- 3. DEINE IMPORT-LOGIK ---
def safe_import(module_name, file_name):
    for path in project_root.rglob(file_name):
        if any(x in str(path) for x in [".venv", "__pycache__", "site-packages"]):
            continue
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    return None

track_mod = safe_import("custom_track", "Track.py")
ui_mod    = safe_import("custom_ui", "ui.py")
wagon_mod = safe_import("custom_wagon", "wagon.py")
cmd_mod   = safe_import("custom_commands", "commands.py")

# ... restlicher Code (get_cls, Flask-Setup etc.) ...


import sys
import os
import threading
import importlib.util
from pathlib import Path


# --- 1. PROJEKT-PFADE ---
# Wir stellen sicher, dass wir im richtigen Verzeichnis suchen (Achterbahn-Unterordner)
current_path = Path(__file__).resolve().parent
project_root = current_path / "Achterbahn" if (current_path / "Achterbahn").exists() else current_path

sys.path.insert(0, str(project_root))
print(f"DEBUG: Suche Dateien in {project_root}")

def safe_import(module_name, file_name):
    """Sucht rekursiv nach der Datei und lädt sie als Modul."""
    for path in project_root.rglob(file_name):
        if any(x in str(path) for x in [".venv", "__pycache__", "site-packages"]):
            continue
        print(f"DEBUG: Lade {module_name} von {path}")
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    return None

# Manuelles Laden der Dateien
track_mod = safe_import("custom_track", "Track.py")
ui_mod    = safe_import("custom_ui", "ui.py")
wagon_mod = safe_import("custom_wagon", "wagon.py")
cmd_mod   = safe_import("custom_commands", "commands.py")

# --- 2. PANDA3D HEADLESS SETUP ---
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none\nload-display none\naudio-library-name null')

# --- 3. KLASSEN-ZUORDNUNG (Mapping) ---
def get_cls(mod, names):
    """Sucht nach einer Klasse im Modul, egal wie sie geschrieben ist."""
    if not mod: return None
    available = dir(mod)
    for name in names:
        for attr in available:
            if attr.lower() == name.lower():
                return getattr(mod, attr)
    return None

# Hier ziehen wir die Klassen exakt aus deiner Track.py
StraightSegment = get_cls(track_mod, ["Straightsegment", "StraightSegment"])
ShortStraightSegment = get_cls(track_mod, ["Shortstraightsegment", "ShortStraightSegment"])
CurveSegment = get_cls(track_mod, ["Curvesegment", "CurveSegment"])
HillUpSegment = get_cls(track_mod, ["Hillupsegment", "HillUpSegment"])
HillDownSegment = get_cls(track_mod, ["Hilldownsegment", "HillDownSegment"])
LoopSegment = get_cls(track_mod, ["Loopsegment", "LoopSegment"])
CorkscrewSegment = get_cls(track_mod, ["Corkscrewsegment", "CorkscrewSegment"])
TrackManager = get_cls(track_mod, ["Trackmanager", "TrackManager"])

ColorPicker = get_cls(ui_mod, ["ColorPicker"])
SegmentPalette = get_cls(ui_mod, ["SegmentPalette"])
TrackControls = get_cls(ui_mod, ["TrackControls"])
Train = get_cls(wagon_mod, ["Train"])

# --- 4. URSINA & FLASK ---
from flask import Flask
import ursina
from ursina import Ursina, Entity, color, Vec3, Sky, camera, Text, destroy, DirectionalLight, AmbientLight
from ursina.prefabs.editor_camera import EditorCamera

web_app = Flask(__name__)
@web_app.route('/')
def health(): return "Achterbahn-Server ist online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# Ursina Konfiguration
is_render = 'RENDER' in os.environ
if is_render:
    ursina.application.window_type = 'none'

app = Ursina(headless=is_render)

# --- 5. GAME LOGIK ---
TRACK_COLORS = {"grau": color.gray, "blau": color.blue, "rot": color.red, "gelb": color.yellow, "lila": color.violet, "schwarz": color.black}

# Die Fabriken nutzen nun die oben sicher gemappten Klassen
SEGMENT_FACTORIES = [
    ("Gerade", lambda c: StraightSegment(c)), ("Gerade kurz", lambda c: ShortStraightSegment(c)),
    ("Hügel rauf", lambda c: HillUpSegment(c)), ("Hügel runter", lambda c: HillDownSegment(c)),
    ("Kurve 90 R", lambda c: CurveSegment(90, "right", c)), ("Kurve 45 R", lambda c: CurveSegment(45, "right", c)),
    ("Kurve 90 L", lambda c: CurveSegment(90, "left", c)), ("Kurve 45 L", lambda c: CurveSegment(45, "left", c)),
    ("Looping", lambda c: LoopSegment(c)), ("Schraube", lambda c: CorkscrewSegment(c))
]

class GameState:
    def __init__(self):
        self.manager = TrackManager() if TrackManager else None
        self.segment_idx = 0
        self.color_key = "schwarz"
        self.running = False
        self._preview = None
        
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
        seg = factory(c)
        if seg:
            self.manager.add_segment(seg)
            self._refresh_preview(); self._update_hud()

    def undo(self):
        if self.manager: self.manager.remove_last()
        self._refresh_preview(); self._update_hud()

    def _refresh_preview(self):
        if self._preview: destroy(self._preview)
        if not StraightSegment: return
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        c = TRACK_COLORS[self.color_key]
        seg = factory(c)
        if seg:
            self._preview = seg.spawn()
            # Transformation aus deiner Trackmanager-Klasse
            if self.manager and hasattr(self.manager, 'apply_exit_transformation'):
                self.manager.apply_exit_transformation(self._preview)

    def _update_hud(self):
        count = len(self.manager.segments) if self.manager else 0
        self._hud.text = f"Teile: {count}\n[SPACE] Place [ENTER] Start/Stop"

# --- 6. UPDATE & INPUT ---
state = None

def update():
    if state and state.running and state.train:
        speed = state.controls.speed if hasattr(state.controls, 'speed') else 1
        state.train.update(speed)

def input(key):
    if not state: return
    if key == "space": state.place()
    elif key == "backspace": state.undo()
    elif key == "enter": state.controls.toggle()

if __name__ == "__main__":
    DirectionalLight().look_at(Vec3(1, -2, 1))
    AmbientLight(color=color.rgba(200, 200, 220, 0.3))
    Entity(model="plane", scale=(1200, 100, 1200), color=color.lime * 0.45)
    Sky()
    state = GameState()
    if not is_render:
        EditorCamera()
    app.run()
