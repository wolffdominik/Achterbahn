"""
train.py – Zugbewegung entlang des Schienenpfades.

Wagen werden als Wireframe (schwarze Konturen, transparente Flächen) gezeichnet:
  - Wagenkasten als 12-Kanten-Quader
  - 4 Räder als Kreise
  - 2 Achsen als Linien
  - 2 Passagierköpfe als Kreise + Arme nach oben
  - Lokomotive: zusätzlicher Frontrahmen
"""

import math

from ursina import Entity, Mesh, Vec3, color, time

from track.track_manager import TrackManager, set_rotation

NUM_WAGONS    = 4
WAGON_SPACING = 0.9   # Abstand zwischen Waggons in Segment-Einheiten
WAGON_HEIGHT  = 0.25  # Wagenmitte über dem Schienenpfad


# ---------------------------------------------------------------------------
# Wireframe-Hilfs-Meshes
# ---------------------------------------------------------------------------

def _box_wireframe(w: float, h: float, d: float, thickness: int = 3) -> Mesh:
    """12 Kanten eines Quaders als GL_LINES-Mesh (Vertex-Paare)."""
    hw, hh, hd = w / 2, h / 2, d / 2
    c = [
        Vec3(-hw, -hh, -hd),  # 0
        Vec3( hw, -hh, -hd),  # 1
        Vec3( hw,  hh, -hd),  # 2
        Vec3(-hw,  hh, -hd),  # 3
        Vec3(-hw, -hh,  hd),  # 4
        Vec3( hw, -hh,  hd),  # 5
        Vec3( hw,  hh,  hd),  # 6
        Vec3(-hw,  hh,  hd),  # 7
    ]
    pairs = [0,1, 1,2, 2,3, 3,0,   # hintere Fläche
             4,5, 5,6, 6,7, 7,4,   # vordere Fläche
             0,4, 1,5, 2,6, 3,7]   # Verbindungskanten
    return Mesh(vertices=[c[i] for i in pairs], mode='line', thickness=thickness)


def _circle_wireframe(radius: float, segments: int = 12,
                      thickness: int = 2) -> Mesh:
    """Kreis in der YZ-Ebene als GL_LINES-Mesh."""
    verts = []
    for i in range(segments):
        a1 = 2 * math.pi * i       / segments
        a2 = 2 * math.pi * (i + 1) / segments
        verts.append(Vec3(0, radius * math.sin(a1), radius * math.cos(a1)))
        verts.append(Vec3(0, radius * math.sin(a2), radius * math.cos(a2)))
    return Mesh(vertices=verts, mode='line', thickness=thickness)


def _line_mesh(*point_pairs: tuple[Vec3, Vec3], thickness: int = 2) -> Mesh:
    """Beliebige Linien als GL_LINES-Mesh aus (Start, Ende)-Paaren."""
    verts = []
    for a, b in point_pairs:
        verts += [a, b]
    return Mesh(vertices=verts, mode='line', thickness=thickness)


# ---------------------------------------------------------------------------
# Wagen-Konstruktion
# ---------------------------------------------------------------------------

def _build_wagon(is_locomotive: bool) -> Entity:
    """
    Baut einen Wagen aus reinen Wireframe-Entities.

    body ist ein unsichtbarer Transform-Container; alle sichtbaren
    Teile sind Kinder davon.  body.enabled = False wird erst am Ende
    gesetzt, damit Ursina alle Kinder vollständig initialisiert.
    """
    body = Entity()
    K = color.black

    # --- Wagenkasten (Quader-Kontur) ---
    Entity(model=_box_wireframe(0.55, 0.30, 0.80, thickness=4),
           color=K, parent=body)

    # --- Räder + Achsen ---
    # Rad: Kreis in YZ-Ebene, Radius 0.10
    # Achse: horizontale Linie von -0.36 bis +0.36
    # Radmitte: 0.10 unter Wagenboden  → body-y = -(0.15 + 0.10) = -0.25
    wheel_y = -0.25
    for wz in (0.28, -0.28):
        # Achse
        Entity(
            model=_line_mesh((Vec3(-0.36, 0, 0), Vec3(0.36, 0, 0)), thickness=2),
            color=K,
            position=(0, wheel_y, wz),
            parent=body,
        )
        # Linkes und rechtes Rad
        for wx in (-0.36, 0.36):
            Entity(
                model=_circle_wireframe(0.10, 14, thickness=3),
                color=K,
                position=(wx, wheel_y, wz),
                parent=body,
            )

    # --- Passagiere: Kopf + Arme ---
    # Kopf: kleiner Kreis, ragt über Wagendach (body_top = +0.15)
    head_y = 0.22   # 0.07 über Wagendach
    for px in (-0.12, 0.12):
        # Kopf
        Entity(
            model=_circle_wireframe(0.065, 8, thickness=2),
            color=K,
            position=(px, head_y, 0.05),
            parent=body,
        )
        # Arme nach oben (je zwei Linien von Schulter zur Hand)
        Entity(
            model=_line_mesh(
                (Vec3(-0.065, 0,    0), Vec3(-0.10, 0.13, 0)),  # linker Arm
                (Vec3( 0.065, 0,    0), Vec3( 0.10, 0.13, 0)),  # rechter Arm
            ),
            color=K,
            position=(px, head_y, 0.05),
            parent=body,
        )

    # --- Lokomotive: zusätzlicher Frontrahmen ---
    if is_locomotive:
        Entity(
            model=_box_wireframe(0.55, 0.30, 0.06, thickness=3),
            color=K,
            position=(0, 0, 0.43),
            parent=body,
        )

    # Erst am Ende deaktivieren – alle Kinder sind bereits initialisiert
    body.enabled = False
    return body


# ---------------------------------------------------------------------------
# Train-Klasse
# ---------------------------------------------------------------------------

class Train:
    """Steuert 4 Waggons, die sich entlang des Schienenpfades bewegen."""

    def __init__(self, manager: TrackManager) -> None:
        self._manager              = manager
        self._seg_t: float         = 0.0
        self._running: bool        = False
        self._wagons: list[Entity] = [
            _build_wagon(is_locomotive=(i == 0)) for i in range(NUM_WAGONS)
        ]

    def start(self) -> None:
        """Setzt den Zug an den Streckenbeginn und startet die Fahrt."""
        if not self._manager.segments:
            return
        self._seg_t   = 0.0
        self._running = True
        for wagon in self._wagons:
            wagon.enabled = True

    def stop(self) -> None:
        """Hält den Zug an und blendet alle Waggons aus."""
        self._running = False
        for wagon in self._wagons:
            wagon.enabled = False

    def update(self, speed: float) -> None:
        """Bewegt alle Waggons einen Frame weiter."""
        if not self._running:
            return
        n = len(self._manager.segments)
        if n == 0:
            return

        self._seg_t = (self._seg_t + speed * time.dt) % n

        for i, wagon in enumerate(self._wagons):
            t_seg    = (self._seg_t - i * WAGON_SPACING) % n
            global_t = t_seg / n
            pos, tangent, up = self._manager.get_world_point(global_t)
            wagon.position = pos + up * WAGON_HEIGHT
            set_rotation(wagon, tangent, up)
