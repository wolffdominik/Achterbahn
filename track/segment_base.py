"""
segment_base.py – Abstrakte Basisklasse für alle Streckenelemente.

Jedes Segment definiert seinen Pfad über get_local_point(t) und
baut daraus automatisch ein zweigleisiges Schienen-Mesh.
"""

from abc import ABC, abstractmethod

from ursina import Entity, Mesh, Vec3


class TrackSegment(ABC):
    """Basis für alle Streckenelemente: Gerade, Kurve, Looping, Schraube."""

    NUM_SAMPLES: int = 40      # Pfad-Auflösung für das Mesh
    RAIL_OFFSET: float = 0.35  # Abstand Mitte ↔ Schienenmitte (halbe Spurweite)
    RAIL_W: float = 0.045      # halbe Schienenbreite  → Schiene ist 0.09 breit
    RAIL_H: float = 0.10       # Schienenhöhe
    SLEEPER_THICKNESS: float = 0.04   # Höhe der Querschwelle
    SLEEPER_DEPTH: float = 0.08       # Tiefe der Querschwelle (entlang Gleis)

    def __init__(self, track_color) -> None:
        self._color = track_color
        self.entity: Entity | None = None

    # ------------------------------------------------------------------
    # Pfad-Interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_local_point(self, t: float) -> tuple[Vec3, Vec3, Vec3]:
        """
        Gibt (position, tangente, oben) im lokalen Koordinatensystem zurück.
        t ∈ [0, 1] — 0 = Einstieg, 1 = Austritt.
        Vektoren müssen nicht normiert sein.
        """
        ...

    # ------------------------------------------------------------------
    # Berechnete Eigenschaften am Segmentaustritt
    # ------------------------------------------------------------------

    @property
    def exit_pos(self) -> Vec3:
        pos, _, _ = self.get_local_point(1.0)
        return pos

    @property
    def exit_tangent(self) -> Vec3:
        _, tangent, _ = self.get_local_point(1.0)
        return tangent.normalized()

    @property
    def exit_up(self) -> Vec3:
        _, _, up = self.get_local_point(1.0)
        return up.normalized()

    # ------------------------------------------------------------------
    # Mesh-Erzeugung: zwei parallele Schienen als Ribbon
    # ------------------------------------------------------------------

    def _build_mesh(self) -> Mesh:
        """
        Erzeugt zwei profilierte Schienen (Rechteck-Querschnitt) + Querschwellen.

        Vertex-Layout je Schiene pro Sample (Indizes relativ zur Schienenbasis):
          0 = bottom-left  1 = bottom-right
          2 = top-right    3 = top-left
        """
        verts: list[Vec3] = []
        tris: list[tuple[int, int, int]] = []

        # --- Zwei Schienen (links/rechts) als extrudiertes Rechteckprofil ---
        for side in (-1, 1):  # -1 = linke Schiene, +1 = rechte Schiene
            offset = side * self.RAIL_OFFSET
            base = len(verts)

            for i in range(self.NUM_SAMPLES + 1):
                t = i / self.NUM_SAMPLES
                pos, tangent, up = self.get_local_point(t)

                tan_n = tangent.normalized()
                up_n  = up.normalized()
                right = up_n.cross(tan_n).normalized()

                center = pos + right * offset
                bl = center - right * self.RAIL_W - up_n * self.RAIL_H * 0.15
                br = center + right * self.RAIL_W - up_n * self.RAIL_H * 0.15
                tr = center + right * self.RAIL_W + up_n * self.RAIL_H * 0.85
                tl = center - right * self.RAIL_W + up_n * self.RAIL_H * 0.85
                verts += [bl, br, tr, tl]

            for i in range(self.NUM_SAMPLES):
                b = base + i * 4
                n = b + 4  # nächster Slice
                # Oberseite
                tris += [(b+3, b+2, n+2), (b+3, n+2, n+3)]
                # Unterseite
                tris += [(b+0, n+0, n+1), (b+0, n+1, b+1)]
                # Linke Seite
                tris += [(b+0, b+3, n+3), (b+0, n+3, n+0)]
                # Rechte Seite
                tris += [(b+1, n+1, n+2), (b+1, n+2, b+2)]

        # --- Querschwellen (Sleepers) ---
        # Schwelle liegt direkt unter den Schienen-Unterkanten
        sleeper_interval = max(1, self.NUM_SAMPLES // 10)
        sw  = self.RAIL_OFFSET + self.RAIL_W + 0.06  # halbe Schwellenlänge
        sh  = self.SLEEPER_THICKNESS
        sd  = self.SLEEPER_DEPTH / 2                  # halbe Tiefe

        for i in range(0, self.NUM_SAMPLES + 1, sleeper_interval):
            t = i / self.NUM_SAMPLES
            pos, tangent, up = self.get_local_point(t)

            tan_n = tangent.normalized()
            up_n  = up.normalized()
            right = up_n.cross(tan_n).normalized()

            # Ankerpunkt = Unterkante der Schiene
            anchor = pos - up_n * self.RAIL_H * 0.15

            b = len(verts)
            # 8 Eckpunkte der Schwellen-Box
            # Schleife: dt ∈ {-sd, +sd}, dy ∈ {0, sh}, dx ∈ {-sw, +sw}
            # Index 0:(−,0,−) 1:(−,0,+) 2:(−,h,−) 3:(−,h,+)
            #        4:(+,0,−) 5:(+,0,+) 6:(+,h,−) 7:(+,h,+)
            for dt in (-sd, sd):
                for dy in (0.0, sh):
                    for dx in (-sw, sw):
                        verts.append(anchor + right * dx + up_n * dy + tan_n * dt)

            tris += [(b+2, b+3, b+7), (b+2, b+7, b+6)]  # oben
            tris += [(b+0, b+4, b+5), (b+0, b+5, b+1)]  # unten
            tris += [(b+4, b+6, b+7), (b+4, b+7, b+5)]  # vorne
            tris += [(b+0, b+1, b+3), (b+0, b+3, b+2)]  # hinten
            tris += [(b+0, b+2, b+6), (b+0, b+6, b+4)]  # links
            tris += [(b+1, b+5, b+7), (b+1, b+7, b+3)]  # rechts

        return Mesh(vertices=verts, triangles=tris, mode="triangle")

    # ------------------------------------------------------------------
    # Ursina-Entity
    # ------------------------------------------------------------------

    def spawn(self) -> Entity:
        """Erstellt die Ursina-Entity mit Schienen-Mesh."""
        self.entity = Entity(
            model=self._build_mesh(),
            color=self._color,
            double_sided=True,
        )
        return self.entity

    def set_color(self, new_color) -> None:
        """Ändert die Schienenfarbe — wirkt sofort auf die Entity."""
        self._color = new_color
        if self.entity:
            self.entity.color = new_color
