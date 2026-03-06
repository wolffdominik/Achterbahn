import sys
import os
import threading
import importlib.util
from pathlib import Path

# --- 1. ABSOLUTER PFAD-FIX & MANUELLER IMPORT ---
# Wir erzwingen, dass Python die Dateien in den Unterordnern findet, 
# egal wie streng das Linux-System auf Render eingestellt ist.
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

# --- 2. PANDA3D / URSINA HEADLESS CONFIG ---
# Diese Zeilen MÜSSEN vor 'from ursina import *' kommen!
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-type none\naudio-library-name null')

# --- 3. KLASSEN-ZUWEISUNG AUS DEN MODULEN ---
if track_mod:
    CorkscrewSegment = track_mod.CorkscrewSegment
    CurveSegment = track_mod.CurveSegment
    HillDownSegment = track_mod.HillDownSegment
    HillUpSegment = track_mod.HillUpSegment
    LoopSegment = track_mod.LoopSegment
    ShortStraightSegment = track_mod.ShortStraightSegment
    StraightSegment = track_mod.StraightSegment
    TrackManager = track_mod.TrackManager
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
# Falls commands.py im Hauptverzeichnis liegt:
try:
    from commands import CommandManager
except ImportError:
    CommandManager = None

# --- 4. WEB-SERVER FÜR RENDER (Health Check) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Achterbahn-Server läuft!", 2
