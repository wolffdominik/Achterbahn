"""
controls.py – Start/Stop-Button und Geschwindigkeits-Slider (rechte Seite).

Der on_toggle-Callback erhält True (Fahrt startet) oder False (Fahrt stoppt).
Der Speed-Wert wird in M5 vom Zugmodul ausgelesen.
"""

from ursina import Button, Entity, Slider, Text, camera, color

X_POS = 0.65
Y_TOP = 0.40


class TrackControls:
    """Start/Stop-Schalter und Geschwindigkeitsregler."""

    def __init__(self, on_toggle) -> None:
        self._on_toggle = on_toggle
        self.running    = False

        # Hintergrundfläche
        Entity(
            model="quad",
            color=color.black66,
            scale=(0.27, 0.28),
            position=(X_POS, Y_TOP - 0.14),
            parent=camera.ui,
        )

        Text(
            text="Steuerung",
            position=(X_POS - 0.125, Y_TOP + 0.025),
            scale=1.0,
            color=color.white,
            parent=camera.ui,
        )

        self._btn = Button(
            text="> Start",
            scale=(0.21, 0.075),
            position=(X_POS, Y_TOP - 0.045),
            color=color.lime,
            highlight_color=color.white,
            radius=0.10,
            parent=camera.ui,
        )
        self._btn.on_click = self.toggle

        Text(
            text="Tempo",
            position=(X_POS - 0.125, Y_TOP - 0.145),
            scale=1.0,
            color=color.white,
            parent=camera.ui,
        )

        # Ursina-Slider: scale steuert die Breite relativ zur Szene
        self.speed_slider = Slider(
            min=0.5,
            max=5.0,
            default=1.5,
            step=0.5,
            dynamic=True,
            scale=0.23,
            position=(X_POS, Y_TOP - 0.20),
            parent=camera.ui,
        )

    def toggle(self) -> None:
        """Wechselt zwischen Fahrt- und Baumodus."""
        self.running = not self.running
        if self.running:
            self._btn.text  = "|| Stop"
            self._btn.color = color.red
        else:
            self._btn.text  = "> Start"
            self._btn.color = color.lime
        self._on_toggle(self.running)

    @property
    def speed(self) -> float:
        """Aktueller Geschwindigkeitswert des Sliders."""
        return self.speed_slider.value
