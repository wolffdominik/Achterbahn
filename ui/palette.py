"""
palette.py – Vertikale Segment-Auswahlleiste (linke Seite).

Jeder Button repräsentiert einen Streckentyp. Der aktive Typ
wird blau hervorgehoben.
"""

from ursina import Button, Entity, Text, camera, color

BUTTON_W = 0.23
BUTTON_H = 0.065
GAP      = 0.008
X_POS    = -0.73
Y_TOP    = 0.40


class SegmentPalette:
    """Vertikale Buttonleiste zur Auswahl des Segmenttyps."""

    def __init__(self, segment_names: list[str], on_select) -> None:
        self._on_select              = on_select
        self._buttons: list[Button] = []

        # Hintergrundfläche passt sich an Anzahl der Buttons an
        bg_h = len(segment_names) * (BUTTON_H + GAP) + 0.07
        Entity(
            model="quad",
            color=color.black66,
            scale=(BUTTON_W + 0.04, bg_h),
            position=(X_POS, Y_TOP - bg_h / 2 + 0.03),
            parent=camera.ui,
        )

        Text(
            text="Schiene",
            position=(X_POS - BUTTON_W / 2 + 0.005, Y_TOP + 0.025),
            scale=1.0,
            color=color.white,
            parent=camera.ui,
        )

        for i, name in enumerate(segment_names):
            y = Y_TOP - i * (BUTTON_H + GAP)
            btn = Button(
                text=name,
                scale=(BUTTON_W, BUTTON_H),
                position=(X_POS, y),
                color=color.dark_gray,
                highlight_color=color.gray,
                radius=0.08,
                parent=camera.ui,
            )
            btn.on_click = (lambda i=i: self._click(i))
            self._buttons.append(btn)

        self._highlight(0)

    def select(self, idx: int) -> None:
        """Aktualisiert die Hervorhebung — z.B. wenn TAB gedrückt wird."""
        self._highlight(idx)

    def _click(self, idx: int) -> None:
        self._highlight(idx)
        self._on_select(idx)

    def _highlight(self, idx: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.color = color.azure if i == idx else color.dark_gray
