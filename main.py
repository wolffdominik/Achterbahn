import sys
import os
from pathlib import Path
import threading

# 1. PFAD-FIX (Zuerst!)
base_path = Path(__file__).resolve().parent
sys.path.insert(0, str(base_path))
sys.path.insert(0, str(base_path / "track"))
sys.path.insert(0, str(base_path / "ui"))
sys.path.insert(0, str(base_path / "wagon"))

# 2. PANDA3D HEADLESS CONFIG (Muss vor Ursina kommen!)
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'audio-library-name null')

# 3. WEITERE IMPORTS
from flask import Flask
from ursina import *
from ursina.prefabs.editor_camera import EditorCamera

# 4. IMPORTS AUS UNTERORDNERN
# Dank sys.path.insert oben können wir sie direkt ansprechen
from Track import (CorkscrewSegment, CurveSegment, HillDownSegment, HillUpSegment, 
                   LoopSegment, ShortStraightSegment, StraightSegment, TrackManager)
from track_manager import set_rotation
from ui import ColorPicker, SegmentPalette, TrackControls
from wagon import Train
from commands import CommandManager

# 5. WEB-SERVER FÜR RENDER (Health Check)
web_app = Flask(__name__)
@web_app.route('/')
def health_check():
    return "Achterbahn-Server läuft!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# 6. URSINA INITIALISIERUNG
is_render = 'RENDER' in os.environ
app = Ursina(headless=is_render, title="Achterbahn Designer")

# 7. KONSTANTEN & SZENEN-LOGIK
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

# 8. GAMESTATE KLASSE
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
        self.palette.select(self.segment_idx)
        self._refresh_preview()
        self._update_hud()

    def next_color(self):
        idx = COLOR_KEYS.index(self.color_key)
        self.color_key = COLOR_KEYS[(idx + 1) % len(COLOR_KEYS)]
        self.color_ui.select(self.color_key)
        self._refresh_preview()
        self._update_hud()

    def _refresh_preview(self):
        if self._preview: destroy(self._preview)
        c = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        preview_seg = factory(color.rgba(c.r, c.g, c.b, 0.35))
        self._preview = preview_seg.spawn()
        self.manager.apply_exit_transform(self._preview)

    def _update_hud(self):
        self._hud.text = f"Teile: {len(self.manager.segments)}\n[RÜCKTASTE] Undo\n[C] Clear\n[ENTER] Start"

# 9
