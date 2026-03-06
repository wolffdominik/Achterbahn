import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. PFAD-REPARATUR (Extrem-Modus) ---
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

def manual_import(name, folder_hint):
    """Sucht rekursiv nach der Datei, falls der Pfad nicht direkt stimmt."""
    # Suche nach Track.py, track.py, Track.py etc.
    search_names = [f"{name}.py", f"{name.lower()}.py", f"{name.capitalize()}.py"]
    
    # 1. Direkter Versuch
    for fname in search_names:
        full_path = current_dir / folder_hint / fname
        if full_path.exists():
            spec = importlib.util.spec_from_file_location(name, str(full_path))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            print(f"ERFOLG: {name} gefunden in {full_path}")
            return module

    # 2. Notfall: Suche im ganzen Projekt
    for path in current_dir.rglob("*.py"):
        if path.name.lower() in [s.lower() for s in search_names]:
            spec = importlib.util.spec_from_file_location(name, str(path))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            print(f"NOTFALL-ERFOLG: {name} gefunden unter {path}")
            return module
            
    print(f"FEHLER: {name} konnte nirgendwo gefunden werden!")
    return None

# Module laden
track_mod = manual_import("Track", "track")
ui_mod = manual_import("ui", "ui")
wagon_mod = manual_import("wagon", "wagon")
commands_mod = manual_import("commands", "track")

# --- 2. GRAFIK-DEAKTIVIERUNG (Bevor irgendwas von Ursina geladen wird) ---
from panda3d.core import loadPrcFileData
# Wir erzwingen 'offscreen' und 'none' auf Systemebene
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'load-display none')
loadPrcFileData('', 'audio-library-name null')
loadPrcFileData('', 'aux-display none')

# --- 3. URSINA & FLASK IMPORTS ---
from flask import Flask
import ursina
from ursina import Ursina, Entity, color, Vec3, DirectionalLight, AmbientLight, Sky, camera, Text, destroy
from ursina.prefabs.editor_camera import EditorCamera

# --- 4. KLASSEN-ZUORDNUNG ---
# Wir nutzen getattr, um Abstürze bei fehlenden Modulen zu verhindern
def get_cls(mod, attr):
    return getattr(mod, attr, getattr(mod, attr.lower(), getattr(mod, attr.capitalize(), None)))

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
CommandManager = get_cls(commands_mod, 'CommandManager')

# --- 5. WEB-SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def health_check(): return "Achterbahn-Server läuft!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# --- 6. URSINA START (Sicherheits-Check für Headless) ---
is_render = 'RENDER' in os.environ
if is_render:
    ursina.application.window_type = 'none'

app = Ursina(headless=is_render)

# --- 7. GAME LOGIC ---
TRACK_COLORS = {"grau": color.gray, "blau": color.blue, "rot": color.red, "gelb": color.yellow, "lila": color.violet, "schwarz": color.black}
COLOR_KEYS = list(TRACK_COLORS.keys())

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
        self.manager.add_segment(factory(c))
        self._refresh_preview(); self._update_hud()

    def undo(self):
        if self.manager: self.manager.remove_last()
        self._refresh_preview(); self._update_hud()

    def _refresh_preview(self):
        if self._preview: destroy(self._preview)
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        c = TRACK_COLORS[self.color_key]
        preview_seg = factory(color.rgba(c.r, c.g, c.b, 0.35))
        self._preview = preview_seg.spawn()
        if self.manager and hasattr(self.manager, 'apply_exit_transformation'):
            self.manager.apply_exit_transformation(self._preview)

    def _update_hud(self):
        self._hud.text = f"Teile: {len(self.manager.segments) if self.manager else 0}\n[ENTER] Start/Stop"

state = None
def update():
    if state and state.running and state.train:
        state.train.update(state.controls.speed if hasattr(state.controls, 'speed') else 1)

if __name__ == "__main__":
    Sky()
    state = GameState()
    app.run()
