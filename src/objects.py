"""Scene object abstractions: Transform, ObjectConfig, SceneObject, and subclasses.

Design principles
-----------------
Config  — what something looks like (colors, mesh references). Immutable,
          shared safely between instances.
Transform — where something is and how it is oriented right now. Mutable,
            owned per-instance.
Class   — how it moves and updates over time. Only subclass when there is
          genuine per-frame behavior, not to work around a transform limitation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

import glm
import numpy as np
from OpenGL.GL import (
    GL_TRIANGLES,
    GL_TRUE,
    glDrawArrays,
    glUniform4f,
    glUniformMatrix4fv,
)

from .particles import ParticleEmitter

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class Drawable(Protocol):
    """Minimal interface expected of every item in Scene.objects."""

    def update(self, dt: float) -> None: ...

    def draw(self) -> None: ...


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Transform:
    """Per-instance mutable placement.

    rotations is a list of (angle_deg, axis) pairs applied left-to-right,
    allowing arbitrary chained rotations without subclassing.

    heading is the explicit Y-axis angle (degrees) maintained alongside
    rotations for any object that faces a direction. Used by _local_to_world
    for emitter anchor math; never derived from rotations by inspection (that
    heuristic silently fails for non-trivial rotation chains).
    """

    pos: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: float = 1.0
    scale_xyz: tuple = None  # overrides scale when non-uniform
    rotations: list = field(default_factory=list)  # [(angle_deg, (rx,ry,rz)), ...]
    heading: float = 0.0  # explicit Y angle for emitter math

    def to_matrix(self) -> np.ndarray:
        m = glm.translate(glm.mat4(1.0), glm.vec3(*self.pos))
        for angle, axis in self.rotations:
            m = glm.rotate(m, math.radians(angle), glm.vec3(*axis))
        sx, sy, sz = self.scale_xyz or (self.scale,) * 3
        m = glm.scale(m, glm.vec3(sx, sy, sz))
        return np.array(m)


@dataclass
class ObjectConfig:
    """Visual identity only — shared safely between instances.

    Intentionally has no transform fields (pos, scale, angle). Those belong
    on Transform. Separating them means a config can be shared between the
    player boat and the horizon boats even though their placement differs.
    """

    default_color: tuple = (1.0, 1.0, 1.0, 1.0)
    part_colors: dict = field(default_factory=dict)
    geometry_parts: dict = None  # name → (start, count)
    geometry_range: tuple = None  # (start, count) for single-mesh objects


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _local_to_world(
    local: tuple,
    scale: float,
    heading_deg: float,
    tx: float,
    ty: float,
    tz: float,
) -> tuple:
    """Transform a local-space point by uniform scale, Y-rotation, translation.

    Matches the transformation order in Transform.to_matrix for the common
    case of a single Y-axis rotation.
    """
    lx, ly, lz = local
    sx, sy, sz = lx * scale, ly * scale, lz * scale
    a = math.radians(heading_deg)
    return (
        sx * math.cos(a) + sz * math.sin(a) + tx,
        sy + ty,
        -sx * math.sin(a) + sz * math.cos(a) + tz,
    )


def _make_emitter(anchor: tuple, **kwargs) -> ParticleEmitter:
    """Construct a ParticleEmitter and set its anchor in one call.

    Used by OrbitalGroup factory lambdas in scene.py so that the anchor and
    the emitter parameters stay co-located at the call site.
    """
    e = ParticleEmitter(**kwargs)
    e.anchor = anchor
    return e


# ---------------------------------------------------------------------------
# Boat constants (used by PlayerBoat and configs.py)
# ---------------------------------------------------------------------------

# Points in boat local space, measured from the model geometry.
CHIMNEY_TOP_LOCAL = (-0.1220, 2.1067, -1.2967)
BOW_LOCAL = (0.0000, -0.6, 2.1089)  # lowered to waterline
BOW_SPRAY_SPEED = 2.0  # sideways component, world units/s
BOW_BACKWARD_SPEED = 2.0  # backward component, world units/s


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class SceneObject:
    """Base scene object.

    Class-level GL uniform locations are set once per program via init_gl().
    Each instance owns a Transform and a list of ParticleEmitters.

    Emitters with a non-None anchor are repositioned each frame in update()
    using _local_to_world — no per-object glue code required in scene.py.
    """

    loc_model: int = None
    loc_color: int = None
    loc_view: int = None
    loc_projection: int = None

    @classmethod
    def init_gl(cls, program: int) -> None:
        from OpenGL.GL import glGetUniformLocation

        cls.loc_model = glGetUniformLocation(program, "model")
        cls.loc_color = glGetUniformLocation(program, "color")
        cls.loc_view = glGetUniformLocation(program, "view")
        cls.loc_projection = glGetUniformLocation(program, "projection")

    def __init__(self, config: ObjectConfig, transform: Transform = None) -> None:
        self.cfg = config
        self.transform = transform or Transform()
        self.emitters: list[ParticleEmitter] = []

    def draw(self) -> None:
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, self.transform.to_matrix())
        if self.cfg.geometry_parts:
            for name, (start, count) in self.cfg.geometry_parts.items():
                glUniform4f(
                    self.loc_color,
                    *self.cfg.part_colors.get(name, self.cfg.default_color),
                )
                glDrawArrays(GL_TRIANGLES, start, count)
        elif self.cfg.geometry_range:
            glUniform4f(self.loc_color, *self.cfg.default_color)
            glDrawArrays(GL_TRIANGLES, *self.cfg.geometry_range)
        for e in self.emitters:
            e.draw(self.loc_model, self.loc_color)

    def update(self, dt: float) -> None:
        for e in self.emitters:
            if e.anchor is not None:
                e.base_pos = list(
                    _local_to_world(
                        e.anchor,
                        self.transform.scale,
                        self.transform.heading,
                        *self.transform.pos,
                    )
                )
            e.update(dt)


# ---------------------------------------------------------------------------
# Behavior subclasses
# ---------------------------------------------------------------------------


class BobbingObject(SceneObject):
    """Animates transform.pos[1] with a two-frequency sine wave.

    Owns its own _time accumulator — no shared elapsed-time state needed.
    The two-frequency wave produces a more natural, irregular bobbing motion
    than a single sine.
    """

    def __init__(
        self,
        config: ObjectConfig,
        transform: Transform = None,
        base_y: float = 0.4,
        amplitude: float = 0.10,
        speed: float = 1.5,
    ) -> None:
        super().__init__(config, transform)
        # NOTE: _time is accumulated dt, not wall-clock time. This differs from
        # the old state.last_frame (which was absolute). Bob phase will diverge
        # if dt is clamped or the session is very long, but is otherwise equivalent.
        self._time = 0.0
        self.base_y = base_y
        self.amplitude = amplitude
        self.speed = speed

    def update(self, dt: float) -> None:
        self._time += dt
        t = self.speed * self._time
        self.transform.pos[1] = self.base_y + self.amplitude * (
            0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
        )
        super().update(dt)


class SpinningSun(SceneObject):
    """Owns its spin angle; no longer reads from state.

    Exists because it has animated per-frame behavior, not because of a
    transform limitation. The fixed tilt and the animated spin are expressed
    as two entries in transform.rotations so no build_matrix override is needed.
    """

    SUN_SPIN_SPEED = 5.0  # degrees per second; moved from state.py

    def __init__(self, config: ObjectConfig, transform: Transform = None) -> None:
        super().__init__(config, transform)
        self._spin = 0.0

    def update(self, dt: float) -> None:
        self._spin += self.SUN_SPIN_SPEED * dt
        self.transform.rotations = [
            (90.0, (1.0, 0.0, 1.0)),  # fixed tilt
            (self._spin, (0.0, 1.0, 0.0)),  # animated spin
        ]
        super().update(dt)


class PlayerBoat(BobbingObject):
    """Player-controlled boat with chimney smoke and bow spray.

    transform.pos, transform.heading, and transform.rotations are written
    each frame by input.process_boat() via the set_target() binding.
    moving_forward is also set by the input handler.

    Bow spray is not reducible to the anchor pattern because its velocity
    depends on heading, so it is computed explicitly in _update_bow_spray().
    """

    def __init__(
        self,
        config: ObjectConfig,
        transform: Transform = None,
        base_y: float = 0.4,
    ) -> None:
        super().__init__(config, transform, base_y=base_y)
        self.moving_forward = False  # set each frame by input handler

        # Emitter params are hardcoded here: PlayerBoat is a singleton and these
        # values won't be reused. For multi-instance objects use the make_emitter
        # factory pattern (as in OrbitalGroup).
        self._smoke = ParticleEmitter(
            base_pos=[0, 0, 0],
            color=(0.55, 0.55, 0.55, 1.0),
            spawn_rate=2.0,
            lifetime=2.0,
            velocity=(0, 1.2, 0),
            max_scale=0.12,
        )
        self._smoke.anchor = CHIMNEY_TOP_LOCAL  # base update() handles repositioning

        self._bow_port = ParticleEmitter(
            base_pos=[0, 0, 0],
            color=(0.9, 0.96, 1.0, 1.0),
            spawn_rate=5.0,
            lifetime=3.0,
            velocity=(0, 0, 0),
            max_scale=0.1,
            drag=1.0,
        )
        self._bow_stbd = ParticleEmitter(
            base_pos=[0, 0, 0],
            color=(0.9, 0.96, 1.0, 1.0),
            spawn_rate=5.0,
            lifetime=3.0,
            velocity=(0, 0, 0),
            max_scale=0.1,
            drag=1.0,
        )
        self.emitters = [self._smoke, self._bow_port, self._bow_stbd]

    def update(self, dt: float) -> None:
        super().update(dt)  # bobs pos[1]; repositions _smoke via anchor
        self._update_bow_spray()

    def _update_bow_spray(self) -> None:
        wx, wy, wz = _local_to_world(
            BOW_LOCAL,
            self.transform.scale,
            self.transform.heading,
            *self.transform.pos,
        )
        a = math.radians(self.transform.heading)
        lat = BOW_SPRAY_SPEED
        bwd = BOW_BACKWARD_SPEED
        self._bow_port.active = self.moving_forward
        self._bow_stbd.active = self.moving_forward
        self._bow_port.base_pos = [wx, wy, wz]
        self._bow_port.velocity = [
            -math.cos(a) * lat - math.sin(a) * bwd,
            0.0,
            math.sin(a) * lat - math.cos(a) * bwd,
        ]
        self._bow_stbd.base_pos = [wx, wy, wz]
        self._bow_stbd.velocity = [
            math.cos(a) * lat - math.sin(a) * bwd,
            0.0,
            -math.sin(a) * lat - math.cos(a) * bwd,
        ]


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class OrbitalGroup:
    """N SceneObject instances on a shared circular orbit.

    Not a SceneObject subclass — it owns N independent instances, each with
    its own Transform. The scene treats it as a Drawable via duck typing:
    same update(dt) / draw() interface, no inheritance required.

    orbit_angle accumulates each frame, replacing state.shark_angle and
    state.horizon_boat_angle. Each instance's position and heading are
    derived from orbit_angle at update time and stored on its Transform —
    so self.instances[i].transform.pos is always meaningful, never stale.
    """

    def __init__(
        self,
        config: ObjectConfig,
        count: int = 3,
        radius: float = 10.0,
        center: tuple = (0.0, 0.0, 0.0),
        speed: float = 2.0,
        facing_offset: float = 0.0,
        make_emitter=None,
        scale: float = 1.0,
    ) -> None:
        self.instances = [
            SceneObject(config, Transform(scale=scale)) for _ in range(count)
        ]
        self.count = count
        self.radius = radius
        self.center = center
        self.speed = speed
        self.facing_offset = facing_offset
        self.orbit_angle = 0.0

        if make_emitter:
            for obj in self.instances:
                obj.emitters.append(make_emitter())

    def update(self, dt: float) -> None:
        self.orbit_angle += self.speed * dt
        for i, obj in enumerate(self.instances):
            deg = self.orbit_angle + i * (360.0 / self.count)
            rad = math.radians(deg)
            obj.transform.pos[0] = self.center[0] + self.radius * math.sin(rad)
            obj.transform.pos[1] = self.center[1]
            obj.transform.pos[2] = self.center[2] + self.radius * math.cos(rad)
            obj.transform.heading = self.facing_offset + deg
            obj.transform.rotations = [(obj.transform.heading, (0, 1, 0))]
            obj.update(dt)  # base class repositions anchored emitters

    def draw(self) -> None:
        for obj in self.instances:
            obj.draw()
