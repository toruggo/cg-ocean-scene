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
| `OrbitalGroup` never creates emitters for its instances | Doc hand-waved emitter creation | Add `make_emitter` factory callable parameter |
| `configs.py` imports `CHIMNEY_TOP_LOCAL` from `scene.py` | Circular dependency risk | Move boat constants to `objects.py` |
| `lm`/`lc` threaded through every constructor | Every object needs the same two uniforms | `SceneObject.init_gl(program)` classmethod; set once |

### v3 problems (review_3.md)

| Problem | Cause | Fix |
|---|---|---|
| `state.py` is a grab bag of unrelated globals | Path-of-least-resistance module everyone imports | Redistribute: constants → classes; per-object state → objects; input state → `input.py`; remnant → `AppState` |
| `PlayerBoat.update()` reads `state.boat_x/z/angle` | Hidden coupling through shared globals | `input.py` holds boat reference via `set_target()`; writes to `target.transform` directly |
| `SpinningSun` reads `state.sun_spin` | Sun spin is per-object state, not application state | `SpinningSun` owns `_spin` and increments it each frame |
| `BobbingObject` reads `state.last_frame` | Accumulated time is per-object state | `BobbingObject` owns `_time` accumulator; increments by `dt` each frame |
| Camera matrices in `state.py` | They never change; they're scene setup, not state | Move to `scene.py.__init__` |

### v4 problems (review_4.md)

| Problem | Cause | Fix |
|---|---|---|
| `set_view_projection` uploads view matrix to model uniform | `loc_model` used instead of `loc_view`/`loc_projection` — silent black-screen bug | Add `loc_view` and `loc_projection` to `SceneObject.init_gl` |
| `coqueiro_scale` in `AppState` | Same pattern as boat: input writes, scene reads via shared state | `set_coqueiros(trees)` in `input.py`; write directly to `tree.transform.scale`; remove `app` from `scene.update` |
| `PlayerBoat` hardcodes emitter parameters | Inconsistent with `OrbitalGroup`'s `make_emitter` pattern everywhere else | Add comment: singleton justification |
| `_make_emitter` referenced but not defined in doc | Omission | Show implementation in `objects.py` section |
| `OrbitalGroup` duck typing undocumented | Contract only implicit | Add `Drawable` Protocol; annotate `self.objects` |

After all fixes, genuine behavior subclasses: `BobbingObject`, `SpinningSun`,
`PlayerBoat` — each exists for per-frame logic, not transform limitations.
`state.py` is gutted and replaced by a minimal `AppState` dataclass.

---

## Target architecture

```
src/
  objects.py   # Transform, ObjectConfig, SceneObject, behavior subclasses,
               # OrbitalGroup, _make_emitter, boat constants
  configs.py   # One ObjectConfig per visual identity
  scene.py     # Wires objects; loops update/draw; owns camera setup
  app.py       # AppState dataclass — the only remaining shared mutable state
  input.py     # Key handlers; set_target(boat); owns keys_pressed + constants
  geometry.py  # Unchanged
  particles.py # +1 line: self.anchor = None
  state.py     # Deleted — contents redistributed
```

---

## `state.py` surgery

`state.py` existed as the path of least resistance — every module imports it,
everyone reads and writes. The object refactor naturally empties it. Here is
where each piece goes.

### Constants → behavior classes

These are not state. They are parameters for specific behaviors and belong
next to the code that uses them.

| Variable | Moves to |
|---|---|
| `BOAT_SPEED = 2.0` | `input.py` |
| `BOAT_ROT = 45.0` | `input.py` |
| `COQUEIRO_SCALE_MIN/MAX/SPEED` | `input.py` |
| `SUN_SPIN_SPEED = 5.0` | `SpinningSun` (class constant) |

### Per-object mutable state → objects own it

| Variable | Moves to |
|---|---|
| `shark_angle` | `OrbitalGroup.orbit_angle` (already) |
| `horizon_boat_angle` | `OrbitalGroup.orbit_angle` (already) |
| `sun_spin` | `SpinningSun._spin` |
| `boat_x/z/angle` | `player_boat.transform` — written by `input.py` |

### Input state → `input.py`

`keys_pressed` and the `boat_moving_forward` flag are the bridge between GLFW
callbacks and game logic. They belong in the module that owns the callbacks.

| Variable | Moves to |
|---|---|
| `keys_pressed` | `input.py` module-level |
| `boat_moving_forward` | `player_boat.moving_forward` — set by `input.py` |

### Camera → `scene.py.__init__`

`STATIC_CAM_POS`, `STATIC_CAM_TARGET`, `mat_view_static`, and `mat_proj_static`
never change. They are scene setup constants, not application state. They move
into `Scene.__init__` as locals and are passed to `set_view_projection`.

### What actually remains: `AppState`

After the above redistribution, one value genuinely crosses the
`input.py` / `scene.py` boundary and has no other clean home:

```python
# src/app.py
from dataclasses import dataclass

@dataclass
class AppState:
    width:     int  = 960
    height:    int  = 720
    wireframe: bool = False
```

`wireframe` is toggled by P in `input.py` and read by the render loop.
`width`/`height` are needed for the projection matrix in `scene.py`.

`coqueiro_scale` is **not** in `AppState`. It follows the same pattern as
`boat_x/z/angle`: input writes it, objects read it. The fix is the same —
`input.py` holds coqueiro references via `set_coqueiros()` and writes directly
to `tree.transform.scale`. No shared state needed.

`delta_time` and `last_frame` are **not** in `AppState`. After the refactor,
`dt` is passed explicitly to every `update(dt)` call, and `BobbingObject` owns
its own `_time` accumulator — no module needs to read a shared elapsed time.

One `AppState` instance is created in `main_scene.py` and passed to anything
that needs it. Functions declare the dependency in their signature instead of
silently reaching into a module.

---

## Core abstractions

### `Transform`

Per-instance mutable placement. Separated from `ObjectConfig` because config
is shared identity (player boat and horizon boat share the same mesh config)
while transform is per-instance state mutated every frame.

The `heading` field is explicit — set alongside `rotations` by any object that
faces a direction. Used by `_local_to_world` for emitter anchor math. Not
derived from `rotations` by inspection (that heuristic silently fails for
non-trivial rotation chains).

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

Base class. Class-level GL uniforms set once via `init_gl`. Owns a `Transform`
and a list of `ParticleEmitter`s.

```python
class SceneObject:
    loc_model:      int = None
    loc_color:      int = None
    loc_view:       int = None
    loc_projection: int = None

    @classmethod
    def init_gl(cls, program):
        cls.loc_model      = glGetUniformLocation(program, "model")
        cls.loc_color      = glGetUniformLocation(program, "color")
        cls.loc_view       = glGetUniformLocation(program, "view")
        cls.loc_projection = glGetUniformLocation(program, "projection")

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

### `ParticleEmitter.anchor`

One-line addition to `particles.py`:

```python
self.anchor = None   # local-space offset; set by owner when needed
```

The anchor lives on the emitter — the thing being positioned — not on the
config. `SceneObject.update()` repositions every emitter with a non-None
anchor. No index magic, any number of anchored emitters per object.

### `_make_emitter`

Helper defined in `objects.py` — constructs a `ParticleEmitter` and sets its
anchor in one call. Used by `OrbitalGroup` factory lambdas in `scene.py`.

```python
def _make_emitter(anchor, **kwargs) -> ParticleEmitter:
    """Construct a ParticleEmitter and set its anchor in one call."""
    e = ParticleEmitter(**kwargs)
    e.anchor = anchor
    return e
```

---

## Behavior subclasses

### `BobbingObject(SceneObject)`

Animates `transform.pos[1]` with a two-frequency sine wave. Owns its own
`_time` accumulator — no shared elapsed-time state needed.

```python
class BobbingObject(SceneObject):
    def __init__(self, config, transform=None,
                 base_y=0.4, amplitude=0.10, speed=1.5):
        super().__init__(config, transform)
        self._time     = 0.0
        self.base_y    = base_y
        self.amplitude = amplitude
        self.speed     = speed

    def update(self, dt):
        # NOTE: _time is accumulated dt, not wall-clock time. This differs from
        # the old state.last_frame (which was absolute). Bob phase will diverge
        # if dt is clamped or the session is very long, but is otherwise equivalent.
        self._time += dt
        t = self.speed * self._time
        self.transform.pos[1] = self.base_y + self.amplitude * (
            0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
        )
        super().update(dt)
```

### `SpinningSun(SceneObject)`

Owns its spin angle and spin speed. No longer reads from `state`. Exists
because it has animated per-frame behavior, not because of a transform limitation.

```python
class SpinningSun(SceneObject):
    SUN_SPIN_SPEED = 5.0   # moved from state.py

    def __init__(self, config, transform=None):
        super().__init__(config, transform)
        self._spin = 0.0

    def update(self, dt):
        self._spin += self.SUN_SPIN_SPEED * dt
        self.transform.rotations = [
            (90.0,        (1.0, 0.0, 1.0)),   # fixed tilt
            (self._spin,  (0.0, 1.0, 0.0)),   # animated spin
        ]
        super().update(dt)
```

### `PlayerBoat(BobbingObject)`

Handles bow spray — two emitters with heading-dependent velocities, not
reducible to the anchor pattern. **Does not read from `state`**. Its
`transform` is written by `input.py` each frame via the `set_target` binding.

```python
class PlayerBoat(BobbingObject):
    def __init__(self, config, transform=None, base_y=0.4):
        super().__init__(config, transform, base_y=base_y)
        self.moving_forward = False   # set each frame by input handler

        # Emitter params are hardcoded here: PlayerBoat is a singleton and these
        # values won't be reused. For multi-instance objects use the make_emitter
        # factory pattern (as in OrbitalGroup).
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
        # transform.pos[0/2], heading, rotations are written by input.process_boat()
        super().update(dt)    # bobs pos[1]; repositions _smoke via anchor
        self._update_bow_spray()

    def _update_bow_spray(self):
        wx, wy, wz = _local_to_world(
            BOW_LOCAL, self.transform.scale,
            self.transform.heading, *self.transform.pos,
        )
        a = math.radians(self.transform.heading)
        lat, bwd = BOW_SPRAY_SPEED, BOW_BACKWARD_SPEED
        self._bow_port.active  = self.moving_forward   # reads own attribute, not state
        self._bow_stbd.active  = self.moving_forward
        self._bow_port.base_pos = [wx, wy, wz]
        self._bow_port.velocity = [-math.cos(a)*lat - math.sin(a)*bwd, 0.0,
                                    math.sin(a)*lat - math.cos(a)*bwd]
        self._bow_stbd.base_pos = [wx, wy, wz]
        self._bow_stbd.velocity = [ math.cos(a)*lat - math.sin(a)*bwd, 0.0,
                                   -math.sin(a)*lat - math.cos(a)*bwd]
```

---

## `input.py`

The input module gains a boat reference and owns the constants that were
previously scattered in `state.py`. It writes directly to the boat's `Transform`
instead of writing to shared globals that `PlayerBoat.update()` would later read.

```python
# src/input.py

BOAT_SPEED           = 2.0    # moved from state.py
BOAT_ROT             = 45.0
COQUEIRO_SCALE_MIN   = 0.01
COQUEIRO_SCALE_MAX   = 0.15
COQUEIRO_SCALE_SPEED = 0.18

keys_pressed = set()   # moved from state.py
_target      = None    # PlayerBoat reference
_coqueiros   = []      # list of coqueiro SceneObjects

def set_target(boat):
    global _target
    _target = boat

def set_coqueiros(trees):
    global _coqueiros
    _coqueiros = list(trees)

def key_event(window, key, scancode, action, mods):
    # (wireframe toggle needs app reference — pass via set_app or module-level)
    if action == glfw.PRESS:
        keys_pressed.add(key)
    elif action == glfw.RELEASE:
        keys_pressed.discard(key)

def process_boat(dt):
    if _target is None:
        return
    if glfw.KEY_A in keys_pressed:
        _target.transform.heading += BOAT_ROT * dt
    if glfw.KEY_D in keys_pressed:
        _target.transform.heading -= BOAT_ROT * dt
    _target.transform.rotations = [(_target.transform.heading, (0, 1, 0))]

    _target.moving_forward = glfw.KEY_W in keys_pressed

    dx = math.sin(math.radians(_target.transform.heading))
    dz = math.cos(math.radians(_target.transform.heading))
    if glfw.KEY_W in keys_pressed:
        _target.transform.pos[0] += dx * BOAT_SPEED * dt
        _target.transform.pos[2] += dz * BOAT_SPEED * dt
    if glfw.KEY_S in keys_pressed:
        _target.transform.pos[0] -= dx * BOAT_SPEED * dt
        _target.transform.pos[2] -= dz * BOAT_SPEED * dt

def process_coqueiro_scale(dt):
    sp = COQUEIRO_SCALE_SPEED * dt
    if glfw.KEY_Z in keys_pressed:
        for tree in _coqueiros:
            tree.transform.scale = min(COQUEIRO_SCALE_MAX, tree.transform.scale + sp)
    if glfw.KEY_X in keys_pressed:
        for tree in _coqueiros:
            tree.transform.scale = max(COQUEIRO_SCALE_MIN, tree.transform.scale - sp)
```

`process_boat` uses `_target.transform.heading` directly — not
`rotations[0][0]` — because `heading` is the explicitly maintained Y-angle
field. `process_coqueiro_scale` writes directly to each tree's
`transform.scale` — same pattern as the boat, no shared state needed.
The coupling between input and scene is now explicit and visible:
`set_target` and `set_coqueiros` document what the input module depends on.

---

## `OrbitalGroup` — a container, not a subclass

`OrbitalGroup` is not a `SceneObject`. It owns N independent `SceneObject`
instances, each with its own `Transform`. The scene treats it via duck typing —
the same `update(dt)` / `draw()` interface as `SceneObject`. This contract is
made explicit with a `Protocol`:

```python
from typing import Protocol

class Drawable(Protocol):
    def update(self, dt: float) -> None: ...
    def draw(self) -> None: ...
```

`Scene.objects` is annotated `list[Drawable]`, so a type checker will catch
it if `OrbitalGroup` ever drifts from the interface.

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
            obj.transform.heading   = self.facing_offset + deg
            obj.transform.rotations = [(obj.transform.heading, (0, 1, 0))]
            obj.update(dt)    # base class repositions anchored emitters

    def draw(self):
        for obj in self.instances:
            obj.draw()
```

**Facing offset:** sharks `0.0`, horizon boats `90.0`.
**`orbit_angle` is owned here** — `state.shark_angle` and
`state.horizon_boat_angle` are gone.

---

## `configs.py`

```python
from . import geometry
from .objects import ObjectConfig

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

---

## `scene.py` — assembly

Camera setup moves here from `state.py`. `update(dt)` takes no `app` —
coqueiro scaling is handled in `input.py` before `update` is called.

```python
class Scene:
    def __init__(self, program, app):
        SceneObject.init_gl(program)

        # Camera — was in state.py; never changes, belongs in scene setup
        cam_pos    = glm.vec3(-24.5841, 8.5859, 11.4405)
        cam_target = glm.vec3(-23.7209, 8.4037, 10.9698)
        self._mat_view = np.array(glm.lookAt(cam_pos, cam_target, glm.vec3(0,1,0)))
        self._mat_proj = np.array(
            glm.perspective(glm.radians(40.0), app.width / app.height, 0.1, 200.0)
        )

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

        volcano = SceneObject(configs.VOLCANO, Transform(pos=[7.0, 1.363, 5.0]))
        volcano.emitters.append(ParticleEmitter(
            base_pos=[7.0, 1.363 + 5.6, 5.0],
            color=(0.30, 0.28, 0.28, 1.0),
            spawn_rate=0.3, lifetime=10.0,
            velocity=(0.0, 0.5, 0.0), max_scale=0.7,
        ))
        self.objects.append(volcano)

    def get_player_boat(self):
        return next(o for o in self.objects if isinstance(o, PlayerBoat))

    def get_coqueiros(self):
        return self._coqueiros

    def update(self, dt):
        for obj in self.objects:
            obj.update(dt)

    def draw_all(self):
        for obj in self.objects:
            obj.draw()

    def set_view_projection(self):
        glUniformMatrix4fv(SceneObject.loc_view,       1, GL_TRUE, self._mat_view)
        glUniformMatrix4fv(SceneObject.loc_projection, 1, GL_TRUE, self._mat_proj)
```

`get_player_boat()` and `get_coqueiros()` are called once in `main_scene.py`
to bind objects to the input handler. `update(dt)` takes no `app` — coqueiro
scaling is handled entirely in `input.py` by the time `update` runs.

---

## `main_scene.py` wiring

```python
app   = AppState()
scene = Scene(program, app)
inp.set_target(scene.get_player_boat())
inp.set_coqueiros(scene.get_coqueiros())

# per-frame loop:
inp.process_boat(dt)
inp.process_coqueiro_scale(dt)
scene.update(dt)
scene.draw_all()
```

---

## What changes

| Module | Change |
|---|---|
| `geometry.py` | None. Clean already. |
| `particles.py` | One line: `self.anchor = None` in `__init__`. |
| `state.py` | **Deleted.** Contents redistributed (see surgery section). |
| `input.py` | Gains `set_target`, `set_coqueiros`, `keys_pressed`, boat/coqueiro constants; writes directly to `target.transform` and `tree.transform.scale`. |
| `main_scene.py` | Creates `AppState`; calls `inp.set_target` and `inp.set_coqueiros`; calls `scene.update(dt)` without `app`. |

---

## Migration steps

Each step leaves the program runnable.

1. **Add `self.anchor = None`** to `ParticleEmitter.__init__`. No behavior change.

2. **Create `src/app.py`** with `AppState`. No other changes yet.

3. **Create `src/objects.py`** — `Transform`, `ObjectConfig`, `SceneObject.init_gl`,
   `BobbingObject`, `SpinningSun`, `PlayerBoat`, `OrbitalGroup`, `_make_emitter`,
   boat constants. Import cleanly; no reference to `state`.

4. **Create `src/configs.py`** — all `ObjectConfig` instances, importing from
   `objects.py` and `geometry.py` only.

5. **Update `input.py`** — add `set_target` and `set_coqueiros`, move `keys_pressed`
   and constants here, rewrite `process_boat` to write to `_target.transform`,
   rewrite `process_coqueiro_scale` to write directly to `tree.transform.scale`.
   Remove `state` imports.

6. **Wire `OrbitalGroup`** for sharks and horizon boats alongside the existing
   scene. Verify orbit positions, facing, and emitter smoke visually.

7. **Wire `PlayerBoat`** with all three emitters. Verify bobbing, chimney smoke,
   and bow spray match existing behavior.

8. **Replace `scene.py`** — swap per-draw-function structure for `self.objects` list;
   move camera setup in; pass `app` to `update`. Full visual regression pass.

9. **Delete `state.py`** — at this point nothing should import it. Fix any remaining
   references. `main_scene.py` creates `AppState`, calls `inp.set_target` and
   `inp.set_coqueiros`, and calls `scene.update(dt)` without `app`.
