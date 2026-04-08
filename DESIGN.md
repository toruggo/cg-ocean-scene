# Scene Architecture Design

## Philosophy

> "The class defines *behavior*, the data comes from outside."

Config says *what* something looks like.
Transform says *where* it is and how it is oriented right now.
Class says *how* it moves and updates over time.
None of these three concerns belongs in the same object.

---

## Design history

### v1 problems (philosophy_2.md)

| Problem | Cause | Fix |
|---|---|---|
| `TiltedObject` exists just to add a second rotation | `build_matrix()` hardcoded one rotation | `Transform.rotations` list; no subclass needed |
| `ObjectConfig` held `pos`, `scale`, `angle` | Transform data mixed with visual identity | Split into `ObjectConfig` (identity) and `Transform` (placement) |
| `OrbitalGroup` mutates `self.pos` in `draw()` | Subclassing one-thing object to draw N | `OrbitalGroup` becomes a container of N `SceneObject` instances |
| Volcano smoke orphaned as a bare `Scene` emitter | "no subclass would reposition it" | Attach emitter to the volcano `SceneObject`; base class handles it |

### v2 problems (review_2.md)

| Problem | Cause | Fix |
|---|---|---|
| `emitter_anchor` on `ObjectConfig` repositions `emitters[0]` | Implicit index contract; config shouldn't know about particles | Move `anchor` to the `ParticleEmitter` itself |
| `y_rotation` property uses `abs(axis[1]) > 0.9` heuristic | `_local_to_world` and `Transform` disagree on rotation model | Delete property; add explicit `transform.heading` field |
| `GrowingObject` is a subclass for one line | `scale_fn` callable wraps a single field assignment | Delete class; set scale in `Scene.update()` before the loop |
| `OrbitalGroup` never creates emitters for its instances | Doc hand-waved emitter creation; parameters have to come from somewhere | Add `make_emitter` factory callable parameter |
| `configs.py` imports `CHIMNEY_TOP_LOCAL` from `scene.py` | Circular dependency risk | Move boat constants to `objects.py` |
| `lm`/`lc` inconsistently passed through constructors | Every object needs the same two uniforms from the same program | `SceneObject.init_gl(program)` classmethod; set once |

After all fixes, genuine behavior subclasses: `BobbingObject`, `SpinningSun`,
`PlayerBoat` — each exists for per-frame logic, not transform limitations.

---

## Target architecture

```
src/
  objects.py   # Transform, ObjectConfig, SceneObject, behavior subclasses,
               # OrbitalGroup, boat constants (CHIMNEY_TOP_LOCAL, BOW_LOCAL)
  configs.py   # One ObjectConfig per visual identity; imports from objects.py
  scene.py     # Wires configs + transforms into objects; loops update/draw
```

`geometry.py`, `state.py`, `input.py` are unchanged.
`particles.py` gets one line: `self.anchor = None` in `ParticleEmitter.__init__`.

---

## Core abstractions

### `Transform`

Per-instance mutable placement. Separated from `ObjectConfig` because config
is shared identity (player boat and horizon boat share the same mesh config)
while transform is per-instance state mutated every frame.

The `heading` field is explicit — it is set alongside `rotations` by any object
that faces a direction. It is the Y-rotation angle used by `_local_to_world`
for emitter anchor math. It is **not** derived from `rotations` by inspection:
that heuristic (v2's `y_rotation` property) silently fails for non-trivial
rotation chains. Keeping them separate is honest about the limitation.

```python
@dataclass
class Transform:
    pos:       list  = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale:     float = 1.0
    scale_xyz: tuple = None                         # overrides scale when non-uniform
    rotations: list  = field(default_factory=list)  # [(angle_deg, (rx,ry,rz)), ...]
    heading:   float = 0.0                          # explicit Y angle for emitter math

    def to_matrix(self) -> np.ndarray:
        m = glm.translate(glm.mat4(1.0), glm.vec3(*self.pos))
        for angle, axis in self.rotations:
            m = glm.rotate(m, math.radians(angle), glm.vec3(*axis))
        sx, sy, sz = self.scale_xyz or (self.scale,) * 3
        m = glm.scale(m, glm.vec3(sx, sy, sz))
        return np.array(m)
```

Coqueiros need no subclass — just two rotation entries and per-instance transforms:

```python
SceneObject(configs.COQUEIRO,
            Transform(pos=[-9.3, 1.998, -6.039],
                      rotations=[(2.3, (0,1,0)), (0.0, (1,0,0))]))
```

### `ObjectConfig`

Visual identity only. Immutable. Shared safely between instances.
No transform fields, no emitter fields.

```python
@dataclass
class ObjectConfig:
    default_color:  tuple = (1.0, 1.0, 1.0, 1.0)
    part_colors:    dict  = field(default_factory=dict)
    geometry_parts: dict  = None     # name → (start, count)
    geometry_range: tuple = None     # (start, count) for single-mesh objects
```

### `SceneObject`

Base class. Class-level GL uniforms set once. Owns a `Transform` and a list
of `ParticleEmitter`s.

```python
class SceneObject:
    loc_model: int = None
    loc_color: int = None

    @classmethod
    def init_gl(cls, program):
        cls.loc_model = glGetUniformLocation(program, "model")
        cls.loc_color = glGetUniformLocation(program, "color")

    def __init__(self, config: ObjectConfig, transform: Transform = None):
        self.cfg       = config
        self.transform = transform or Transform()
        self.emitters  = []

    def draw(self):
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, self.transform.to_matrix())
        if self.cfg.geometry_parts:
            for name, (start, count) in self.cfg.geometry_parts.items():
                glUniform4f(self.loc_color,
                            *self.cfg.part_colors.get(name, self.cfg.default_color))
                glDrawArrays(GL_TRIANGLES, start, count)
        elif self.cfg.geometry_range:
            glUniform4f(self.loc_color, *self.cfg.default_color)
            glDrawArrays(GL_TRIANGLES, *self.cfg.geometry_range)
        for e in self.emitters:
            e.draw(self.loc_model, self.loc_color)

    def update(self, dt):
        for e in self.emitters:
            if e.anchor is not None:
                e.base_pos = list(_local_to_world(
                    e.anchor,
                    self.transform.scale,
                    self.transform.heading,
                    *self.transform.pos,
                ))
            e.update(dt)
```

The `update()` loop repositions every emitter whose `.anchor` is set, in any
order, with no index assumptions. Multiple anchored emitters on the same object
work correctly.

### `ParticleEmitter.anchor`

One-line addition to `particles.py`:

```python
# In ParticleEmitter.__init__:
self.anchor = None   # local-space offset; set by owner when needed
```

When `anchor` is not None, `SceneObject.update()` calls `_local_to_world` to
compute the world-space `base_pos` each frame. The anchor lives on the emitter —
the thing being positioned — not on the config, which describes visual identity
and should not know about particle systems.

---

## Behavior subclasses

### `BobbingObject(SceneObject)`

Animates `transform.pos[1]` with a two-frequency sine wave. Any floating object.

```python
class BobbingObject(SceneObject):
    def __init__(self, config, transform=None,
                 base_y=0.4, amplitude=0.10, speed=1.5):
        super().__init__(config, transform)
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

Updates `transform.rotations` from state each frame. Exists for animated
behavior, not for a transform limitation.

```python
class SpinningSun(SceneObject):
    def update(self, dt):
        self.transform.rotations = [
            (90.0,           (1.0, 0.0, 1.0)),  # fixed tilt
            (state.sun_spin, (0.0, 1.0, 0.0)),  # animated spin
        ]
        super().update(dt)
```

The sun has no emitters so `heading` is never used; no need to set it.

### `PlayerBoat(BobbingObject)`

Syncs position and facing from `state`. Handles bow spray, which requires two
emitters with heading-dependent velocities — not reducible to the anchor pattern.

```python
class PlayerBoat(BobbingObject):
    def __init__(self, config, transform=None, base_y=0.4):
        super().__init__(config, transform, base_y=base_y)
        self._smoke    = ParticleEmitter(base_pos=[0,0,0], color=(0.55,0.55,0.55,1),
                                         spawn_rate=2.0, lifetime=2.0,
                                         velocity=(0,1.2,0), max_scale=0.12)
        self._smoke.anchor = CHIMNEY_TOP_LOCAL   # base update() handles repositioning

        self._bow_port = ParticleEmitter(base_pos=[0,0,0], color=(0.9,0.96,1,1),
                                         spawn_rate=5.0, lifetime=3.0,
                                         velocity=(0,0,0), max_scale=0.1, drag=1.0)
        self._bow_stbd = ParticleEmitter(base_pos=[0,0,0], color=(0.9,0.96,1,1),
                                         spawn_rate=5.0, lifetime=3.0,
                                         velocity=(0,0,0), max_scale=0.1, drag=1.0)
        self.emitters = [self._smoke, self._bow_port, self._bow_stbd]

    def update(self, dt):
        self.transform.pos[0] = state.boat_x
        self.transform.pos[2] = state.boat_z
        self.transform.heading   = state.boat_angle   # explicit; used by smoke anchor
        self.transform.rotations = [(state.boat_angle, (0, 1, 0))]
        super().update(dt)    # bobs pos[1]; repositions _smoke via anchor
        self._update_bow_spray()

    def _update_bow_spray(self):
        wx, wy, wz = _local_to_world(
            BOW_LOCAL, self.transform.scale,
            self.transform.heading, *self.transform.pos,
        )
        a = math.radians(self.transform.heading)
        lat, bwd = BOW_SPRAY_SPEED, BOW_BACKWARD_SPEED
        self._bow_port.active  = state.boat_moving_forward
        self._bow_stbd.active  = state.boat_moving_forward
        self._bow_port.base_pos = [wx, wy, wz]
        self._bow_port.velocity = [-math.cos(a)*lat - math.sin(a)*bwd, 0.0,
                                    math.sin(a)*lat - math.cos(a)*bwd]
        self._bow_stbd.base_pos = [wx, wy, wz]
        self._bow_stbd.velocity = [ math.cos(a)*lat - math.sin(a)*bwd, 0.0,
                                   -math.sin(a)*lat - math.cos(a)*bwd]
```

`_smoke.anchor` is set on the emitter itself; `super().update(dt)` uses
`transform.heading` to reposition it correctly. Only bow spray needs explicit
code because its velocity depends on heading and it has two emitters at the same
anchor point — the single-emitter pattern doesn't fit.

---

## `OrbitalGroup` — a container, not a subclass

`OrbitalGroup` is not a `SceneObject`. It owns N independent `SceneObject`
instances, each with its own `Transform`. The scene treats it as a duck-typed
object with `update(dt)` and `draw()`.

`make_emitter` is an optional factory callable that creates one `ParticleEmitter`
per instance. Emitter parameters (color, lifetime, etc.) differ between object
types, so they belong at the call site, not hardcoded in `OrbitalGroup`.

```python
class OrbitalGroup:
    def __init__(self, config, count=3, radius=10.0, center=(0,0,0),
                 speed=2.0, facing_offset=0.0, make_emitter=None):
        self.instances     = [SceneObject(config) for _ in range(count)]
        self.count         = count
        self.radius        = radius
        self.center        = center
        self.speed         = speed
        self.facing_offset = facing_offset
        self.orbit_angle   = 0.0

        if make_emitter:
            for obj in self.instances:
                obj.emitters.append(make_emitter())

    def update(self, dt):
        self.orbit_angle += self.speed * dt
        for i, obj in enumerate(self.instances):
            deg = self.orbit_angle + i * (360.0 / self.count)
            rad = math.radians(deg)
            obj.transform.pos[0]    = self.center[0] + self.radius * math.sin(rad)
            obj.transform.pos[2]    = self.center[2] + self.radius * math.cos(rad)
            obj.transform.heading   = self.facing_offset + deg   # explicit
            obj.transform.rotations = [(obj.transform.heading, (0, 1, 0))]
            obj.update(dt)    # base class repositions anchored emitters

    def draw(self):
        for obj in self.instances:
            obj.draw()
```

**Facing offset:**
- Sharks `facing_offset=0.0` — fin mesh naturally faces travel direction
- Horizon boats `facing_offset=90.0` — boat mesh needs +90° to face tangent

**`orbit_angle` is owned here**, updated via `speed * dt`. The old
`state.shark_angle` and `state.horizon_boat_angle` globals become unused.

---

## `configs.py`

`CHIMNEY_TOP_LOCAL` and `BOW_LOCAL` live in `objects.py` (not `scene.py`),
so `configs.py` can import them without a circular dependency.

```python
from . import geometry
from .objects import ObjectConfig   # no CHIMNEY_TOP_LOCAL needed here

SEA = ObjectConfig(
    default_color=(0.05, 0.35, 0.65, 1.0),
    geometry_range=(geometry.start_sea, geometry.count_sea),
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
    part_colors={
        "boat_bottom": (1.000, 0.608, 0.000, 1.0),
        "boat_top":    (0.922, 0.890, 0.537, 1.0),
        "cabin":       (1.000, 0.788, 0.000, 1.0),
        "cabin_top":   (1.000, 0.882, 0.000, 1.0),
        "chimney":     (1.000, 0.608, 0.000, 1.0),
    },
)
HORIZON_BOAT = ObjectConfig(        # same mesh as PLAYER_BOAT, different look
    geometry_parts=geometry.boat_parts,
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
)
```

No `emitter_anchor` fields anywhere — anchors live on the emitters.

---

## `scene.py` — assembly

```python
class Scene:
    def __init__(self, program):
        SceneObject.init_gl(program)    # sets loc_model, loc_color once

        coqueiro_transforms = [
            Transform(pos=[-9.300, 1.998, -6.039], rotations=[(2.3,  (0,1,0)), (0.0,  (1,0,0))]),
            Transform(pos=[-6.989, 0.772, -3.975], rotations=[(27.0, (0,1,0)), (30.0, (1,0,0))]),
            Transform(pos=[-10.566, 0.839, -5.779], rotations=[(-75.8,(0,1,0)), (30.0, (1,0,0))]),
        ]
        self._coqueiros = [SceneObject(configs.COQUEIRO, t) for t in coqueiro_transforms]

        self.objects = [
            SceneObject(configs.SEA,        Transform(scale_xyz=(40.0, 1.0, 50.0))),
            SceneObject(configs.ISLAND,     Transform(pos=[-7.0, 0.839, -6.0],  scale=1.5)),
            SceneObject(configs.LIGHTHOUSE, Transform(pos=[-7.0, 2.124, -6.0],  scale=0.3)),
            SpinningSun(configs.SUN,        Transform(pos=[20.0, 12.0, -15.0],  scale=2.0)),
            *self._coqueiros,
            PlayerBoat(configs.PLAYER_BOAT, Transform(scale=0.6), base_y=0.4),
            OrbitalGroup(configs.HORIZON_BOAT, count=3, radius=40.0, speed=2.0,
                         facing_offset=90.0,
                         make_emitter=lambda: _make_emitter(
                             anchor=CHIMNEY_TOP_LOCAL,
                             color=(0.60, 0.60, 0.65, 1.0),
                             spawn_rate=1.5, lifetime=6.0,
                             velocity=(0.0, 1.0, 0.0), max_scale=0.10,
                         )),
            OrbitalGroup(configs.SHARK_FIN, count=3, radius=3.0, speed=25.0,
                         facing_offset=0.0,
                         make_emitter=lambda: _make_emitter(
                             anchor=(0.0, 0.0, 0.0),
                             color=(0.75, 0.88, 1.0, 1.0),
                             spawn_rate=8.0, lifetime=1.5,
                             velocity=(0.0, 0.0, 0.0), max_scale=0.04,
                         )),
        ]

        # Volcano: static emitter, world pos never changes, no anchor needed
        volcano = SceneObject(configs.VOLCANO, Transform(pos=[7.0, 1.363, 5.0]))
        volcano.emitters.append(ParticleEmitter(
            base_pos=[7.0, 1.363 + 5.6, 5.0],
            color=(0.30, 0.28, 0.28, 1.0),
            spawn_rate=0.3, lifetime=10.0,
            velocity=(0.0, 0.5, 0.0), max_scale=0.7,
        ))
        self.objects.append(volcano)

    def update(self, dt):
        for tree in self._coqueiros:
            tree.transform.scale = state.coqueiro_scale   # explicit; no subclass
        for obj in self.objects:
            obj.update(dt)

    def draw_all(self):
        for obj in self.objects:
            obj.draw()

    def set_view_projection(self, mat_view, mat_proj):
        glUniformMatrix4fv(SceneObject.loc_model, 1, GL_TRUE, mat_view)    # reuse uniform locs
        glUniformMatrix4fv(SceneObject.loc_projection, 1, GL_TRUE, mat_proj)
```

`_make_emitter` is a small helper in `objects.py` that constructs a
`ParticleEmitter` and sets its `anchor` attribute:

```python
def _make_emitter(anchor=None, **kwargs) -> ParticleEmitter:
    e = ParticleEmitter(**kwargs)
    e.anchor = anchor
    return e
```

Coqueiro scale is three lines in `Scene.update()`, not a subclass. Everyone can
read it. Adding a new scene object is one line in `__init__`. No new draw method.

---

## What does NOT change

| Module | Change |
|---|---|
| `geometry.py` | None. Clean already. |
| `state.py` | Remove `shark_angle`, `horizon_boat_angle` — owned by each `OrbitalGroup` now. |
| `particles.py` | One line: `self.anchor = None` in `__init__`. |
| `input.py` | Remove updates to the two deleted state globals. |
| `main_scene.py` | Calls `scene.update(dt)` and `scene.draw_all()` — interface unchanged. |

---

## Migration steps

Each step leaves the program runnable.

1. **Add `self.anchor = None`** to `ParticleEmitter.__init__`. No behavior change.

2. **Create `src/objects.py`** — `Transform`, `ObjectConfig`, `SceneObject.init_gl`,
   `BobbingObject`, `SpinningSun`, `PlayerBoat`, `OrbitalGroup`, `_make_emitter`,
   and the boat constants (`CHIMNEY_TOP_LOCAL`, `BOW_LOCAL`).

3. **Create `src/configs.py`** — all `ObjectConfig` instances, importing from
   `objects.py` and `geometry.py` only.

4. **Wire `OrbitalGroup`** for sharks and horizon boats alongside the existing
   scene. Verify orbit positions, facing, and emitter smoke visually.

5. **Wire `PlayerBoat`** with all three emitters. Verify bobbing, chimney smoke,
   and bow spray match existing behavior.

6. **Replace `scene.py`** — swap the per-draw-function structure for the
   `self.objects` list. Full visual regression pass.

7. **Remove dead globals** — `shark_angle` and `horizon_boat_angle` from
   `state.py`, and the code in `input.py` that updated them.
