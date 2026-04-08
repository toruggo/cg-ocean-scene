# Scene Architecture Design

## Philosophy

> "The class defines *behavior*, the data comes from outside."

Config says *what* something looks like and where it starts.
Transform says *where* it is and how it is oriented right now.
Class says *how* it moves and updates over time.
None of these three concerns belongs in the same object.

---

## Problems in the original DESIGN.md (v1)

The first version made several mistakes that philosophy_2.md corrects:

| Problem | Cause | Fix |
|---|---|---|
| `TiltedObject` exists just to add a second rotation | `build_matrix()` was too rigid — one rotation hardcoded | `Transform.rotations` list; no subclass needed |
| `ObjectConfig` held `pos`, `scale`, `angle` | Transform data mixed with visual identity | Split into `ObjectConfig` (identity) and `Transform` (placement) |
| `OrbitalGroup` mutates `self.pos` in `draw()` | Subclassing an object that draws one thing to draw N | `OrbitalGroup` becomes a container owning N `SceneObject` instances |
| Volcano smoke orphaned as a bare emitter on `Scene` | "no subclass whose `update()` would reposition it" — but base class already does | Attach emitter to the volcano's `SceneObject`; base class handles it |

After fixes, only three genuine behavior subclasses remain:
`BobbingObject`, `SpinningSun`, `PlayerBoat` — each exists because it has
per-frame logic, not because the base class couldn't express its transform.

---

## Target architecture

```
src/
  objects.py   # Transform, ObjectConfig, SceneObject, behavior subclasses, OrbitalGroup
  configs.py   # One ObjectConfig per visual identity
  scene.py     # Wires configs + transforms into objects; loops update/draw
```

`geometry.py`, `state.py`, `particles.py`, `input.py` are unchanged.

---

## Core abstractions

### `Transform`

A composable, mutable value object that owns an object's current placement.
Separated from `ObjectConfig` because config is shared between instances
(the player boat and a horizon boat can share the same mesh/colors config)
while transform is per-instance and mutated every frame.

```python
@dataclass
class Transform:
    pos:       list  = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale:     float = 1.0
    scale_xyz: tuple = None                    # overrides scale when non-uniform
    rotations: list  = field(default_factory=list)  # [(angle_deg, (rx,ry,rz)), ...]

    def to_matrix(self) -> np.ndarray:
        m = glm.translate(glm.mat4(1.0), glm.vec3(*self.pos))
        for angle, axis in self.rotations:
            m = glm.rotate(m, math.radians(angle), glm.vec3(*axis))
        sx, sy, sz = self.scale_xyz or (self.scale,) * 3
        m = glm.scale(m, glm.vec3(sx, sy, sz))
        return np.array(m)

    @property
    def y_rotation(self) -> float:
        """Return the first Y-axis rotation angle, or 0. Used for emitter anchoring."""
        for angle, axis in self.rotations:
            if abs(axis[1]) > 0.9:
                return angle
        return 0.0
```

With `rotations` as a list, coqueiros need no subclass — just two entries:

```python
tree.transform.rotations = [(2.3, (0,1,0)), (0.0, (1,0,0))]
```

### `ObjectConfig`

Visual identity only. Immutable. Shared safely between instances.
No transform fields.

```python
@dataclass
class ObjectConfig:
    default_color:  tuple = (1.0, 1.0, 1.0, 1.0)
    part_colors:    dict  = field(default_factory=dict)
    geometry_parts: dict  = None          # name → (start, count)
    geometry_range: tuple = None          # (start, count) for single-mesh objects
    emitter_anchor: tuple = None          # local-space point for a follow-emitter
```

`emitter_anchor` is the local-space point (e.g. chimney top) that the base
`SceneObject.update()` transforms to world space and uses to reposition
`emitters[0]` each frame. This handles smoke on horizon boats with no subclass.

### `SceneObject`

Base class. Holds a config and a transform. Owns a list of `ParticleEmitter`s.

```python
class SceneObject:
    def __init__(self, config: ObjectConfig, loc_model, loc_color,
                 transform: Transform = None):
        self.cfg       = config
        self.transform = transform or Transform()
        self.loc_model = loc_model
        self.loc_color = loc_color
        self.emitters  = []

    def draw(self):
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, self.transform.to_matrix())
        if self.cfg.geometry_parts:
            for name, (start, count) in self.cfg.geometry_parts.items():
                glUniform4f(self.loc_color, *self.cfg.part_colors.get(name, self.cfg.default_color))
                glDrawArrays(GL_TRIANGLES, start, count)
        elif self.cfg.geometry_range:
            glUniform4f(self.loc_color, *self.cfg.default_color)
            glDrawArrays(GL_TRIANGLES, *self.cfg.geometry_range)
        for e in self.emitters:
            e.draw(self.loc_model, self.loc_color)

    def update(self, dt):
        if self.cfg.emitter_anchor and self.emitters:
            self.emitters[0].base_pos = list(_local_to_world(
                self.cfg.emitter_anchor,
                self.transform.scale,
                self.transform.y_rotation,
                *self.transform.pos,
            ))
        for e in self.emitters:
            e.update(dt)
```

---

## Behavior subclasses

Only three. Each exists because it has genuine per-frame logic.

### `BobbingObject(SceneObject)`

Animates `transform.pos[1]` with a two-frequency sine wave.
Any water-floating object inherits this.

```python
class BobbingObject(SceneObject):
    def __init__(self, config, loc_model, loc_color, transform=None,
                 base_y=0.4, amplitude=0.10, speed=1.5):
        super().__init__(config, loc_model, loc_color, transform)
        self.base_y    = base_y
        self.amplitude = amplitude
        self.speed     = speed

    def update(self, dt):
        t = self.speed * state.last_frame
        self.transform.pos[1] = self.base_y + self.amplitude * (
            0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
        )
        super().update(dt)
```

### `SpinningSun(SceneObject)`

Exists because it updates `transform.rotations` from state each frame.
Not because of a transform limitation — `Transform` can express this natively.

```python
class SpinningSun(SceneObject):
    def update(self, dt):
        self.transform.rotations = [
            (90.0,            (1.0, 0.0, 1.0)),   # fixed tilt
            (state.sun_spin,  (0.0, 1.0, 0.0)),   # animated spin
        ]
        super().update(dt)
```

### `PlayerBoat(BobbingObject)`

Syncs position and heading from `state` each frame. Also handles bow spray,
which has two emitters whose velocities depend on heading direction and cannot
be reduced to the single `emitter_anchor` pattern.

```python
class PlayerBoat(BobbingObject):
    def __init__(self, config, loc_model, loc_color, transform=None, base_y=0.4):
        super().__init__(config, loc_model, loc_color, transform, base_y=base_y)
        self._smoke     = ParticleEmitter(base_pos=[0,0,0], ...)
        self._bow_port  = ParticleEmitter(base_pos=[0,0,0], ...)
        self._bow_stbd  = ParticleEmitter(base_pos=[0,0,0], ...)
        self.emitters   = [self._smoke, self._bow_port, self._bow_stbd]

    def update(self, dt):
        self.transform.pos[0]    = state.boat_x
        self.transform.pos[2]    = state.boat_z
        self.transform.rotations = [(state.boat_angle, (0,1,0))]
        super().update(dt)   # bobs pos[1], repositions smoke via emitter_anchor
        self._update_bow_spray()

    def _update_bow_spray(self):
        wx, wy, wz = _local_to_world(BOW_LOCAL, ..., *self.transform.pos)
        angle_rad = math.radians(state.boat_angle)
        lat, bwd  = BOW_SPRAY_SPEED, BOW_BACKWARD_SPEED
        self._bow_port.active  = state.boat_moving_forward
        self._bow_stbd.active  = state.boat_moving_forward
        self._bow_port.base_pos = [wx, wy, wz]
        self._bow_port.velocity = [
            -math.cos(angle_rad) * lat - math.sin(angle_rad) * bwd, 0.0,
             math.sin(angle_rad) * lat - math.cos(angle_rad) * bwd,
        ]
        self._bow_stbd.base_pos = [wx, wy, wz]
        self._bow_stbd.velocity = [
             math.cos(angle_rad) * lat - math.sin(angle_rad) * bwd, 0.0,
            -math.sin(angle_rad) * lat - math.cos(angle_rad) * bwd,
        ]
```

`PLAYER_BOAT` config includes `emitter_anchor=CHIMNEY_TOP_LOCAL` so
`super().update(dt)` repositions `emitters[0]` (the smoke) automatically.
Only bow spray needs explicit code.

---

## `OrbitalGroup` — a container, not a subclass

The v1 design had `OrbitalGroup` as a `SceneObject` subclass that mutated
`self.pos` and `self.angle` in a loop inside `draw()`. This left `self.pos`
pointing to the last instance after every draw — meaningless and fragile.

`OrbitalGroup` is not a `SceneObject`. It owns N independent `SceneObject`
instances, each with its own `Transform`. It updates them and forwards
`draw()` calls. The scene treats it like any other object via duck typing.

```python
class OrbitalGroup:
    def __init__(self, config, loc_model, loc_color,
                 count=3, radius=10.0, center=(0,0,0),
                 speed=2.0, facing_offset=0.0):
        self.instances     = [
            SceneObject(config, loc_model, loc_color) for _ in range(count)
        ]
        self.count         = count
        self.radius        = radius
        self.center        = center
        self.speed         = speed
        self.facing_offset = facing_offset
        self.orbit_angle   = 0.0

    def update(self, dt):
        self.orbit_angle += self.speed * dt
        for i, obj in enumerate(self.instances):
            deg = self.orbit_angle + i * (360.0 / self.count)
            rad = math.radians(deg)
            obj.transform.pos[0]    = self.center[0] + self.radius * math.sin(rad)
            obj.transform.pos[2]    = self.center[2] + self.radius * math.cos(rad)
            obj.transform.rotations = [(self.facing_offset + deg, (0,1,0))]
            obj.update(dt)   # handles emitter_anchor repositioning if set

    def draw(self):
        for obj in self.instances:
            obj.draw()
```

**Facing offset:**
- Sharks: `facing_offset=0.0` — fin mesh naturally faces travel direction
- Horizon boats: `facing_offset=90.0` — boat mesh needs +90° to face tangent

**Emitters on orbital instances:**
Because `SceneObject.update()` handles `emitter_anchor` repositioning using the
instance's current `transform`, each orbital instance can have a smoke emitter
with zero extra code. `HORIZON_BOAT` config sets `emitter_anchor=CHIMNEY_TOP_LOCAL`;
the base class does the rest.

For shark trail emitters, no local offset is needed — the trail follows the fin's
world position directly. Set `emitter_anchor=(0, 0, 0)` in `SHARK_FIN` config and
the base class will call `_local_to_world((0,0,0), ...)`, which equals `transform.pos`.

---

## Coqueiro: scale animation

Coqueiros grow over time via `state.coqueiro_scale`. The three instances share the
same config and geometry but each has its own two-rotation transform. The scale
update is genuine per-frame behavior, so it belongs in a subclass:

```python
class GrowingObject(SceneObject):
    """Object whose scale is driven by a state variable each frame."""
    def __init__(self, config, loc_model, loc_color, transform=None, scale_fn=None):
        super().__init__(config, loc_model, loc_color, transform)
        self.scale_fn = scale_fn

    def update(self, dt):
        if self.scale_fn:
            self.transform.scale = self.scale_fn()
        super().update(dt)
```

Used as:
```python
GrowingObject(configs.COQUEIRO, lm, lc,
              transform=Transform(pos=[...], rotations=[...]),
              scale_fn=lambda: state.coqueiro_scale)
```

---

## `configs.py`

```python
from . import geometry
from .objects import ObjectConfig
from .scene   import CHIMNEY_TOP_LOCAL   # or move constant to objects.py

SEA = ObjectConfig(
    default_color=(0.05, 0.35, 0.65, 1.0),
    geometry_range=(geometry.start_sea, geometry.count_sea),
    # scale_xyz lives in the Transform, not here — Transform(scale_xyz=(40,1,50))
)

ISLAND = ObjectConfig(
    default_color=(0.76, 0.70, 0.50, 1.0),
    geometry_range=(geometry.start_island, geometry.count_island),
)

VOLCANO = ObjectConfig(
    default_color=(0.35, 0.30, 0.28, 1.0),
    geometry_range=(geometry.start_volcano, geometry.count_volcano),
)

SUN = ObjectConfig(
    default_color=(1.0, 0.85, 0.10, 1.0),
    geometry_range=(geometry.start_sun, geometry.count_sun),
)

LIGHTHOUSE = ObjectConfig(
    geometry_parts=geometry.lh_parts,
    part_colors={
        "lighthouse_body":      (0.980, 0.361, 0.361, 1.0),
        "Cylinder.001":         (0.992, 0.541, 0.420, 1.0),
        "lighthouse_top_floor": (0.996, 0.761, 0.533, 1.0),
        "lighthouse_light":     (0.984, 0.937, 0.463, 1.0),
    },
)

COQUEIRO = ObjectConfig(
    geometry_parts=geometry.coqueiro_parts,
    part_colors={
        "tronco": (0.42, 0.30, 0.20, 1.0),
        "folhas": (0.18, 0.62, 0.28, 1.0),
    },
)

PLAYER_BOAT = ObjectConfig(
    geometry_parts=geometry.boat_parts,
    emitter_anchor=CHIMNEY_TOP_LOCAL,    # base class repositions smoke emitter
    part_colors={
        "boat_bottom": (1.000, 0.608, 0.000, 1.0),
        "boat_top":    (0.922, 0.890, 0.537, 1.0),
        "cabin":       (1.000, 0.788, 0.000, 1.0),
        "cabin_top":   (1.000, 0.882, 0.000, 1.0),
        "chimney":     (1.000, 0.608, 0.000, 1.0),
    },
)

HORIZON_BOAT = ObjectConfig(            # same mesh as PLAYER_BOAT, different look
    geometry_parts=geometry.boat_parts,
    emitter_anchor=CHIMNEY_TOP_LOCAL,
    part_colors={
        "boat_bottom": (0.22, 0.22, 0.22, 1.0),
        "boat_top":    (0.30, 0.30, 0.30, 1.0),
        "cabin":       (0.28, 0.28, 0.28, 1.0),
        "cabin_top":   (0.25, 0.25, 0.25, 1.0),
        "chimney":     (0.18, 0.18, 0.18, 1.0),
    },
)

SHARK_FIN = ObjectConfig(
    default_color=(0.25, 0.25, 0.30, 1.0),
    geometry_range=(geometry.start_fin, geometry.count_fin),
    emitter_anchor=(0.0, 0.0, 0.0),     # trail emitter follows the fin's world pos
)
```

`SEA` has no `pos` or `scale` fields — those go into `Transform` at scene assembly.
This makes clear that scale and position are per-instance concerns, not identity.

---

## `scene.py` — assembly

```python
class Scene:
    def __init__(self, program):
        lm = glGetUniformLocation(program, "model")
        lc = glGetUniformLocation(program, "color")

        self.objects = [
            SceneObject(configs.SEA,
                        transform=Transform(scale_xyz=(40.0, 1.0, 50.0))),
            SceneObject(configs.ISLAND,
                        transform=Transform(pos=[-7.0, 0.839, -6.0], scale=1.5)),
            SceneObject(configs.VOLCANO,
                        transform=Transform(pos=[7.0, 1.363, 5.0])),
            SceneObject(configs.LIGHTHOUSE,
                        transform=Transform(pos=[-7.0, 2.124, -6.0], scale=0.3)),
            SpinningSun(configs.SUN,
                        transform=Transform(pos=[20.0, 12.0, -15.0], scale=2.0)),
            # Three coqueiros — same config, different per-instance transforms
            GrowingObject(configs.COQUEIRO, lm, lc,
                          transform=Transform(pos=[-9.300, 1.998, -6.039],
                                             rotations=[(2.3, (0,1,0)), (0.0, (1,0,0))]),
                          scale_fn=lambda: state.coqueiro_scale),
            GrowingObject(configs.COQUEIRO, lm, lc,
                          transform=Transform(pos=[-6.989, 0.772, -3.975],
                                             rotations=[(27.0, (0,1,0)), (30.0, (1,0,0))]),
                          scale_fn=lambda: state.coqueiro_scale),
            GrowingObject(configs.COQUEIRO, lm, lc,
                          transform=Transform(pos=[-10.566, 0.839, -5.779],
                                             rotations=[(-75.8, (0,1,0)), (30.0, (1,0,0))]),
                          scale_fn=lambda: state.coqueiro_scale),
            PlayerBoat(configs.PLAYER_BOAT, lm, lc,
                       transform=Transform(scale=0.6), base_y=0.4),
            OrbitalGroup(configs.HORIZON_BOAT, lm, lc,
                         count=3, radius=40.0, speed=2.0, facing_offset=90.0),
            OrbitalGroup(configs.SHARK_FIN, lm, lc,
                         count=3, radius=3.0,  speed=25.0, facing_offset=0.0),
        ]

        # Volcano smoke: static emitter, world pos never changes
        volcano = next(o for o in self.objects if o.cfg is configs.VOLCANO)
        volcano.emitters.append(ParticleEmitter(
            base_pos=[7.0, 1.363 + 5.6, 5.0],
            color=(0.30, 0.28, 0.28, 1.0),
            spawn_rate=0.3, lifetime=10.0,
            velocity=(0.0, 0.5, 0.0), max_scale=0.7,
        ))

    def update(self, dt):
        for obj in self.objects:
            obj.update(dt)

    def draw_all(self):
        for obj in self.objects:
            obj.draw()

    def set_view_projection(self, mat_view, mat_proj):
        glUniformMatrix4fv(self.loc_view, 1, GL_TRUE, mat_view)
        glUniformMatrix4fv(self.loc_projection, 1, GL_TRUE, mat_proj)
```

Adding a new object is one `__init__` line. No new `draw_X()` method, no wiring
in `draw_all`.

---

## What does NOT change

| Module | Reason |
|---|---|
| `geometry.py` | Clean already. Mesh loading and `model_matrix()` are not the problem. |
| `particles.py` | `ParticleEmitter` is well-contained. |
| `state.py` | Mostly unchanged. `shark_angle` and `horizon_boat_angle` become unused and are removed — their state is now owned by each `OrbitalGroup` instance. |
| `input.py` | No changes needed. |
| `main_scene.py` | Calls `scene.update(dt)` and `scene.draw_all()` — interface unchanged. |

---

## Migration steps

Each step leaves the program runnable.

1. **Create `src/objects.py`** — `Transform`, `ObjectConfig`, `SceneObject`,
   `BobbingObject`, `GrowingObject`, `SpinningSun`, `PlayerBoat`, `OrbitalGroup`.
   No imports from `scene.py`. Verify with a simple import.

2. **Create `src/configs.py`** — all `ObjectConfig` instances. Verify each
   references the correct `geometry_parts` or `geometry_range`.

3. **Bring up `OrbitalGroup`** for sharks and horizon boats alongside the existing
   scene. Verify orbit positions, facing, and emitter smoke visually match.

4. **Bring up `PlayerBoat`** with all three emitters. Verify bobbing, chimney smoke,
   and bow spray match existing behavior.

5. **Replace `scene.py`** — swap per-function draw code for the `self.objects` list.
   Run and do a full visual regression pass.

6. **Remove dead globals** from `state.py` (`shark_angle`, `horizon_boat_angle`)
   and the code in `input.py` / `main_scene.py` that updated them.
