"""
segments.py – Konkrete Streckenelemente.

Alle Segmente starten bei (0, 0, 0) mit Tangente (0, 0, 1).
Der TrackManager (M3) transformiert sie in die korrekte Weltposition.

Koordinatensystem:  X = rechts,  Y = oben,  Z = vorwärts
"""

import math

from ursina import Vec3

from .segment_base import TrackSegment


class StraightSegment(TrackSegment):
    """Gerade Strecke der Länge 4."""

    LENGTH: float = 4.0

    def get_local_point(self, t: float) -> tuple[Vec3, Vec3, Vec3]:
        return (
            Vec3(0, 0, t * self.LENGTH),
            Vec3(0, 0, 1),
            Vec3(0, 1, 0),
        )


class ShortStraightSegment(StraightSegment):
    """Kurze Gerade — halb so lang wie eine normale Gerade (Länge 2)."""

    LENGTH: float = 2.0


class CurveSegment(TrackSegment):
    """
    Horizontale Kurve (45° oder 90°) nach links oder rechts.

    Der Kreisradius beträgt 3 Units. Eintritt und Austritt
    liegen in der Horizontalen (y = 0).
    """

    RADIUS: float = 3.0

    def __init__(self, angle_deg: float, direction: str, track_color) -> None:
        """
        angle_deg : Kurvenwinkel — 45 oder 90
        direction : 'left' oder 'right'
        """
        super().__init__(track_color)
        self._angle_rad = math.radians(angle_deg)
        self._direction = direction

    def get_local_point(self, t: float) -> tuple[Vec3, Vec3, Vec3]:
        R = self.RADIUS
        α = self._angle_rad       # Gesamtwinkel des Bogens

        if self._direction == "right":
            # Mittelpunkt bei (R, 0, 0); Bogenstartwinkel π
            θ = math.pi - α * t
            x = R + R * math.cos(θ)
            z = R * math.sin(θ)
            tx = α * R * math.sin(θ)   # d/dt x
            tz = -α * R * math.cos(θ)  # d/dt z
        else:
            # Mittelpunkt bei (-R, 0, 0); Bogenstartwinkel 0
            θ = α * t
            x = -R + R * math.cos(θ)
            z = R * math.sin(θ)
            tx = -α * R * math.sin(θ)
            tz = α * R * math.cos(θ)

        return Vec3(x, 0, z), Vec3(tx, 0, tz), Vec3(0, 1, 0)


class HillUpSegment(TrackSegment):
    """
    Hügel nach oben: startet waagrecht, steigt sanft an und endet waagrecht
    auf einer um HEIGHT erhöhten Ebene.

    Profil: y(t) = HEIGHT/2 * (1 - cos(π·t))
    → Ableitung am Start/Ende = 0 (waagrechte Tangente), Maximum in der Mitte.
    """

    HEIGHT: float = 3.0   # Höhenunterschied zwischen Ein- und Austritt
    LENGTH: float = 6.0   # horizontale Länge des Segments

    def get_local_point(self, t: float) -> tuple[Vec3, Vec3, Vec3]:
        H, L = self.HEIGHT, self.LENGTH
        y  =  H / 2 * (1 - math.cos(math.pi * t))
        z  =  L * t
        dy =  H / 2 * math.pi * math.sin(math.pi * t)   # d(y)/dt
        dz =  L                                           # d(z)/dt = konstant
        # up senkrecht zur Tangente in der YZ-Ebene → Wagen neigt sich mit dem Hang
        return Vec3(0, y, z), Vec3(0, dy, dz), Vec3(0, dz, -dy)


class HillDownSegment(TrackSegment):
    """
    Hügel nach unten: startet waagrecht, senkt sich sanft ab und endet
    waagrecht auf einer um HEIGHT abgesenkten Ebene.

    Spiegelbild von HillUpSegment in Y-Richtung.
    """

    HEIGHT: float = 3.0
    LENGTH: float = 6.0

    def get_local_point(self, t: float) -> tuple[Vec3, Vec3, Vec3]:
        H, L = self.HEIGHT, self.LENGTH
        y  = -H / 2 * (1 - math.cos(math.pi * t))
        z  =  L * t
        dy = -H / 2 * math.pi * math.sin(math.pi * t)
        dz =  L
        return Vec3(0, y, z), Vec3(0, dy, dz), Vec3(0, dz, -dy)


class LoopSegment(TrackSegment):
    """
    Vertikaler 360°-Looping in der YZ-Ebene.

    Eintritt und Austritt liegen beide bei (0, 0, 0) mit
    Tangente (0, 0, 1) — das Segment kehrt geometrisch zur
    Ausgangsposition zurück.
    """

    RADIUS: float = 2.5

    def get_local_point(self, t: float) -> tuple[Vec3, Vec3, Vec3]:
        R = self.RADIUS
        θ = 2 * math.pi * t

        pos = Vec3(0, R * (1 - math.cos(θ)), R * math.sin(θ))

        tangent = Vec3(
            0,
            R * 2 * math.pi * math.sin(θ),
            R * 2 * math.pi * math.cos(θ),
        )

        # Oben zeigt zum Loopmittelpunkt (Fliehkraft-Richtung für den Fahrer)
        loop_center = Vec3(0, R, 0)
        up = (loop_center - pos).normalized()

        return pos, tangent, up


class CorkscrewSegment(TrackSegment):
    """
    Schraube: die Spur spiralisiert 360° um die Vorwärtsachse.

    Position und Ausstiegspunkt liegen beide auf der Z-Achse;
    die Tangente am Austritt weicht leicht von (0,0,1) ab
    (der TrackManager berücksichtigt dies beim Verketten).
    """

    RADIUS: float = 1.2
    LENGTH: float = 10.0

    def get_local_point(self, t: float) -> tuple[Vec3, Vec3, Vec3]:
        R = self.RADIUS
        L = self.LENGTH
        θ = 2 * math.pi * t

        pos = Vec3(R * math.sin(θ), R * (1 - math.cos(θ)), L * t)

        tangent = Vec3(
            R * 2 * math.pi * math.cos(θ),
            R * 2 * math.pi * math.sin(θ),
            L,
        )

        # Oben zeigt radial zum Drehmittelpunkt der Spirale
        spiral_center = Vec3(0, R, pos.z)
        up = spiral_center - pos
        if up.length() < 0.001:
            up = Vec3(0, 1, 0)
        else:
            up = up.normalized()

        return pos, tangent, up
