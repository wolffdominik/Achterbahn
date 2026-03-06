"""
track_manager.py – Verwaltet die Strecke als verkettete Segment-Liste.

Kernprinzip: Jedes Segment wird in einem "Welt-Rahmen" platziert
(Position + Richtungsvektoren). Beim Anhängen eines neuen Segments
wird der Rahmen mit dem lokalen Austritt des aktuellen Segments
weitergeschoben.
"""

from panda3d.core import LMatrix3f, LQuaternionf

from ursina import Entity, Vec3, destroy

from .segment_base import TrackSegment


# ---------------------------------------------------------------------------
# Hilfsfunktionen (modul-privat)
# ---------------------------------------------------------------------------

def _rot(v: Vec3, world_fwd: Vec3, world_up: Vec3) -> Vec3:
    """Rotiert lokalen Vektor v (X=rechts, Y=oben, Z=vorwärts) in den Weltrahmen."""
    right = world_up.cross(world_fwd).normalized()
    return right * v.x + world_up * v.y + world_fwd * v.z


def set_rotation(entity: Entity, forward: Vec3, up: Vec3) -> None:
    """
    Setzt die Rotation der Entity so, dass lokales +Z → forward und +Y → up zeigt.

    Verwendet Panda3D-Quaternionen (row-vector-Konvention):
    Zeilen der Matrix = Zielbasisvektoren (right, up, forward).
    """
    right = up.cross(forward).normalized()
    up_o  = forward.cross(right).normalized()   # up ⊥ forward sicherstellen

    mat = LMatrix3f(
        right.x,   right.y,   right.z,
        up_o.x,    up_o.y,    up_o.z,
        forward.x, forward.y, forward.z,
    )
    q = LQuaternionf()
    q.setFromMatrix(mat)
    entity.setQuat(q)


# ---------------------------------------------------------------------------
# TrackManager
# ---------------------------------------------------------------------------

class TrackManager:
    """Verwaltet alle Streckenelemente und deren Weltkoordinaten."""

    def __init__(self) -> None:
        self.segments: list[TrackSegment] = []

        # Aktueller Weltrahmen am Streckenende
        self._w_pos: Vec3 = Vec3(0, 0, 0)
        self._w_fwd: Vec3 = Vec3(0, 0, 1)
        self._w_up:  Vec3 = Vec3(0, 1, 0)

        # Einstiegs-Rahmen jedes Segments (für get_world_point + undo)
        self._entry_frames: list[tuple[Vec3, Vec3, Vec3]] = []

    # ------------------------------------------------------------------
    # Öffentliches Interface
    # ------------------------------------------------------------------

    def add_segment(self, segment: TrackSegment) -> TrackSegment:
        """Platziert *segment* nahtlos am aktuellen Streckenende."""
        self._entry_frames.append((Vec3(self._w_pos), Vec3(self._w_fwd), Vec3(self._w_up)))

        entity = segment.spawn()
        entity.position = Vec3(self._w_pos)
        set_rotation(entity, self._w_fwd, self._w_up)

        self._advance(segment)
        self.segments.append(segment)
        return segment

    def remove_last(self) -> None:
        """Entfernt das zuletzt hinzugefügte Segment."""
        if not self.segments:
            return
        seg = self.segments.pop()
        if seg.entity:
            destroy(seg.entity)
        # Weltrahmen auf den Einstieg des entfernten Segments zurücksetzen
        if self._entry_frames:
            pos, fwd, up = self._entry_frames.pop()
            self._w_pos, self._w_fwd, self._w_up = Vec3(pos), Vec3(fwd), Vec3(up)

    def clear(self) -> None:
        """Löscht die gesamte Strecke."""
        for seg in self.segments:
            if seg.entity:
                destroy(seg.entity)
        self.segments.clear()
        self._entry_frames.clear()
        self._w_pos = Vec3(0, 0, 0)
        self._w_fwd = Vec3(0, 0, 1)
        self._w_up  = Vec3(0, 1, 0)

    def get_world_point(self, global_t: float) -> tuple[Vec3, Vec3, Vec3]:
        """
        Gibt (position, tangente, oben) entlang der Gesamtstrecke zurück.
        global_t ∈ [0, 1] — wird in M5 für die Waggon-Bewegung verwendet.
        """
        if not self.segments:
            return Vec3(0, 0, 0), Vec3(0, 0, 1), Vec3(0, 1, 0)

        t_s     = global_t * len(self.segments)
        seg_idx = min(int(t_s), len(self.segments) - 1)
        local_t = t_s - seg_idx

        e_pos, e_fwd, e_up = self._entry_frames[seg_idx]
        l_pos, l_tan, l_up = self.segments[seg_idx].get_local_point(local_t)

        return (
            e_pos + _rot(l_pos, e_fwd, e_up),
            _rot(l_tan, e_fwd, e_up).normalized(),
            _rot(l_up,  e_fwd, e_up).normalized(),
        )

    def apply_exit_transform(self, entity: Entity) -> None:
        """Positioniert eine Entity exakt am aktuellen Streckenausgang.
        Nützlich für die Vorschau des nächsten Segments.
        """
        entity.position = Vec3(self._w_pos)
        set_rotation(entity, self._w_fwd, self._w_up)

    # ------------------------------------------------------------------
    # Interna
    # ------------------------------------------------------------------

    def _advance(self, segment: TrackSegment) -> None:
        """Schiebt den Weltrahmen zum Austritt des gerade platzierten Segments."""
        new_pos = self._w_pos + _rot(segment.exit_pos,     self._w_fwd, self._w_up)
        new_fwd = _rot(segment.exit_tangent, self._w_fwd, self._w_up).normalized()
        new_up  = _rot(segment.exit_up,      self._w_fwd, self._w_up).normalized()
        self._w_pos, self._w_fwd, self._w_up = new_pos, new_fwd, new_up
