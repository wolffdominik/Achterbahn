"""
color_picker.py – Horizontale Farbauswahl (untere Bildschirmkante).

Sechs farbige Quadrate; das aktive wird vergrößert dargestellt.
"""

from ursina import Button, Entity, Text, camera, color

SWATCH = 0.062
GAP    = 0.010
Y_POS  = -0.43


class ColorPicker:
    """Reihe farbiger Schaltflächen zur Schienenfarb-Auswahl."""

    def __init__(self, track_colors: dict, on_select) -> None:
        self._on_select              = on_select
        self._keys                   = list(track_colors.keys())
        self._colors                 = track_colors
        self._buttons: list[Button] = []

        n       = len(self._keys)
        total_w = n * (SWATCH + GAP) - GAP
        x0      = -total_w / 2 + SWATCH / 2

        Entity(
            model="quad",
            color=color.black66,
            scale=(total_w + 0.06, SWATCH + 0.05),
            position=(0, Y_POS),
            parent=camera.ui,
        )

        Text(
            text="Farbe",
            position=(-total_w / 2 - 0.02, Y_POS + SWATCH / 2 + 0.005),
            scale=1.0,
            color=color.white,
            parent=camera.ui,
        )

        for i, key in enumerate(self._keys):
            x = x0 + i * (SWATCH + GAP)
            btn = Button(
                text="",
                scale=(SWATCH, SWATCH),
                position=(x, Y_POS),
                color=track_colors[key],
                highlight_color=color.white,
                radius=0.12,
                parent=camera.ui,
            )
            btn.on_click = (lambda i=i: self._click(i))
            self._buttons.append(btn)

        self._highlight(0)

    def select(self, key: str) -> None:
        """Aktualisiert die Hervorhebung — z.B. wenn Q gedrückt wird."""
        idx = self._keys.index(key)
        self._highlight(idx)

    def _click(self, idx: int) -> None:
        self._highlight(idx)
        self._on_select(self._keys[idx])

    def _highlight(self, idx: int) -> None:
        """Das aktive Farbfeld wird leicht vergrößert dargestellt."""
        for i, btn in enumerate(self._buttons):
            s = SWATCH * 1.3 if i == idx else SWATCH
            btn.scale = (s, s)
