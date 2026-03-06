"""
main.py – Achterbahn Designer
Einstiegspunkt: Ursina-App, 3D-Szene, UI und interaktiver Streckenbau.

Tastaturkürzel (alternativ zu den UI-Buttons):
    LEERTASTE        Segment platzieren
    RÜCKTASTE        Letztes Segment rückgängig machen
    TAB              Nächster Segmenttyp
    Q                Nächste Farbe
    C                Gesamte Strecke löschen
    ENTER            Start / Stop umschalten

Starten:
    python Achterbahn/main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ursina import *
from ursina.prefabs.editor_camera import EditorCamera

from track import CorkscrewSegment, CurveSegment, HillDownSegment, HillUpSegment, LoopSegment, ShortStraightSegment, StraightSegment, TrackManager
from track.track_manager import set_rotation
from ui import ColorPicker, SegmentPalette, TrackControls
from wagon import Train

app = Ursina(headless=True)
# ---------------------------------------------------------------------------
# Globale Farb-Konstanten für Schienen
# ---------------------------------------------------------------------------

TRACK_COLORS: dict[str, color] = {
    "grau":    color.gray,
    "blau":    color.blue,
    "rot":     color.red,
    "gelb":    color.yellow,
    "lila":    color.violet,
    "schwarz": color.black,
}

DEFAULT_COLOR_KEY = "schwarz"

# Alle wählbaren Segmenttypen: (Anzeigename, Factory-Funktion)
SEGMENT_FACTORIES: list[tuple[str, object]] = [
    ("Gerade",       lambda c: StraightSegment(c)),
    ("Gerade kurz",  lambda c: ShortStraightSegment(c)),
    ("Hügel rauf",   lambda c: HillUpSegment(c)),
    ("Hügel runter", lambda c: HillDownSegment(c)),
    ("Kurve 90  R",  lambda c: CurveSegment(90, "right", c)),
    ("Kurve 45  R",  lambda c: CurveSegment(45, "right", c)),
    ("Kurve 90  L",  lambda c: CurveSegment(90, "left",  c)),
    ("Kurve 45  L",  lambda c: CurveSegment(45, "left",  c)),
    ("Looping",      lambda c: LoopSegment(c)),
    ("Schraube",     lambda c: CorkscrewSegment(c)),
]

COLOR_KEYS = list(TRACK_COLORS.keys())


# ---------------------------------------------------------------------------
# Szene
# ---------------------------------------------------------------------------

def create_ground() -> Entity:
    """Grüner Rasenboden."""
    return Entity(
        model="plane",
        scale=(1200, 100, 1200),
        color=color.lime * 0.45,
    )


def setup_lighting() -> None:
    """Direktionales Sonnenlicht + weiches Umgebungslicht."""
    sun = DirectionalLight()
    sun.look_at(Vec3(1, -2, 1))
    AmbientLight(color=color.rgba(200, 200, 220, 0.3))


# ---------------------------------------------------------------------------
# Spielzustand
# ---------------------------------------------------------------------------

class GameState:
    """Kapselt Strecke, Auswahl, UI-Komponenten, Vorschau und Laufzustand."""

    def __init__(self) -> None:
        self.manager     = TrackManager()
        self.segment_idx = 0
        self.color_key   = DEFAULT_COLOR_KEY
        self.running     = False

        self._preview: Entity | None = None

        # UI-Komponenten erstellen und Callbacks verdrahten
        seg_names    = [name for name, _ in SEGMENT_FACTORIES]
        self.palette  = SegmentPalette(seg_names, self.set_segment_type)
        self.color_ui = ColorPicker(TRACK_COLORS, self.set_color)
        self.controls = TrackControls(self._on_toggle)

        # Minimales HUD: Stückzahl + Undo/Clear-Hinweise
        self._hud = Text(
            text="",
            position=(-0.85, -0.38),
            scale=1.1,
            background=False,
            parent=camera.ui,
        )

        # Zug erstellen (Waggons zunächst unsichtbar)
        self.train = Train(self.manager)

        self._update_hud()
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Aktionen über UI-Buttons
    # ------------------------------------------------------------------

    def set_segment_type(self, idx: int) -> None:
        """Wird vom Palette-Button aufgerufen."""
        self.segment_idx = idx
        self._refresh_preview()
        self._update_hud()

    def set_color(self, key: str) -> None:
        """Wird vom Farbwähler aufgerufen."""
        self.color_key = key
        self._refresh_preview()
        self._update_hud()

    def _on_toggle(self, running: bool) -> None:
        """Wird vom Start/Stop-Button aufgerufen."""
        self.running = running
        if running:
            self.train.start()
        else:
            self.train.stop()

    # ------------------------------------------------------------------
    # Aktionen über Tastaturkürzel
    # ------------------------------------------------------------------

    def place(self) -> None:
        """Platziert das ausgewählte Segment am Streckenende."""
        c       = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        self.manager.add_segment(factory(c))
        self._refresh_preview()
        self._update_hud()

    def undo(self) -> None:
        """Entfernt das zuletzt gebaute Segment."""
        self.manager.remove_last()
        self._refresh_preview()
        self._update_hud()

    def clear_track(self) -> None:
        """Löscht die gesamte Strecke und stoppt den Zug."""
        self.train.stop()
        if self.running:
            self.running = False
            self.controls.toggle()   # Button auf "> Start" zurücksetzen
        self.manager.clear()
        self._refresh_preview()
        self._update_hud()

    def next_type(self) -> None:
        """Tastenkürzel TAB: nächster Typ; synchronisiert Palette."""
        self.segment_idx = (self.segment_idx + 1) % len(SEGMENT_FACTORIES)
        self.palette.select(self.segment_idx)
        self._refresh_preview()
        self._update_hud()

    def next_color(self) -> None:
        """Tastenkürzel Q: nächste Farbe; synchronisiert Farbwähler."""
        idx            = COLOR_KEYS.index(self.color_key)
        self.color_key = COLOR_KEYS[(idx + 1) % len(COLOR_KEYS)]
        self.color_ui.select(self.color_key)
        self._refresh_preview()
        self._update_hud()

    def toggle_run(self) -> None:
        """Tastenkürzel ENTER: Start/Stop umschalten."""
        self.controls.toggle()   # toggle() aktualisiert self.running via Callback

    # ------------------------------------------------------------------
    # Vorschau-Entity
    # ------------------------------------------------------------------

    def _refresh_preview(self) -> None:
        """Transparente Vorschau des nächsten Segments am Streckenausgang."""
        if self._preview:
            destroy(self._preview)

        c               = TRACK_COLORS[self.color_key]
        factory         = SEGMENT_FACTORIES[self.segment_idx][1]
        preview_seg     = factory(color.rgba(c.r, c.g, c.b, 0.35))
        self._preview   = preview_seg.spawn()
        self.manager.apply_exit_transform(self._preview)

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------

    def _update_hud(self) -> None:
        n = len(self.manager.segments)
        self._hud.text = (
            f"Teile: {n}\n"
            f"[RÜCKTASTE] Rückgängig\n"
            f"[C] Alles löschen\n"
            f"[ENTER] Start / Stop"
        )


# ---------------------------------------------------------------------------
# Ursina-Frame-Handler (wird automatisch jeden Frame aufgerufen)
# ---------------------------------------------------------------------------

# Vorab-Deklaration, damit update() auch ohne state nicht crasht
state: "GameState | None" = None


def update() -> None:
    """Bewegt den Zug jeden Frame, wenn die Fahrt läuft."""
    if state and state.running:
        state.train.update(state.controls.speed)


# ---------------------------------------------------------------------------
# Ursina-Eingabe-Handler
# ---------------------------------------------------------------------------

def input(key: str) -> None:
    if   key == "space":     state.place()
    elif key == "backspace": state.undo()
    elif key == "tab":       state.next_type()
    elif key == "q":         state.next_color()
    elif key == "c":         state.clear_track()
    elif key == "enter":     state.toggle_run()


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = Ursina(title="Achterbahn Designer", borderless=False)

    window.size = (1280, 720)
    window.center_on_screen()
    window.fps_counter.enabled = True

    setup_lighting()
    create_ground()
    Sky()

    state = GameState()

    # Orbit-Kamera: linke Maustaste = drehen, rechte = schwenken, Scroll = zoomen
    EditorCamera()

    app.run()
