# Scene Architecture Design

## Philosophy

> "The class defines *behavior*, the data comes from outside."
> — philosophy.md

A `Boat` that can only ever be orange is a disguised constant, not a reusable object.
The clean split is: **dataclass for configuration, class for behavior**.

Config says *what* something looks like and where it starts.
Class says *how* something moves and updates.
Neither knows about the other's concerns.

---

## Current problems

| Symptom | Root cause |
|---|---|
| `BOAT_PART_COLORS`, `LH_PART_COLORS`, etc. are class-level dicts on `Scene` | Visual identity is baked into behavior code |
| `draw_boat()` mixes matrix math, GL calls, and particle positioning | Draw functions have multiple responsibilities |
| Adding a new object requires a new `draw_X()` method and wiring in `draw_all()` | No uniform object protocol |
| Player boat and horizon boats share the same mesh but can't share code | Config and behavior are fused |

---

## Target architecture

Three new modules replace the monolithic `scene.py`:

```
src/
  objects.py   # ObjectConfig dataclass + SceneObject base + behavior subclasses
  configs.py   # One ObjectConfig instance per visual identity
  scene.py     # Scene.__init__ wires configs into objects; draw_all loops
```

`geometry.py`, `state.py`, `particles.py`, and `input.py` are **unchanged**.

---

## `objects.py`

### `ObjectConfig`

```python
@dataclass
class ObjectConfig:
    pos:            tuple = (0.0, 0.0, 0.0)
    scale:          float = 1.0
    scale_xyz:      tuple | None = None        # overrides scale when non-uniform (e.g. sea)
    angle:          float = 0.0
    default_color:  tuple = (1.0, 1.0, 1.0, 1.0)
    part_colors:    dict  = field(default_factory=dict)
    geometry_parts: dict  = None               # multi-part mesh: name → (start, count)
    geometry_range: tuple = None               # single mesh: (start, count)
```

`scale_xyz` exists only for the sea (sx=40, sy=1, sz=50). All other objects use
uniform `scale`. `SceneObject.build_matrix()` checks `scale_xyz` first.

### `SceneObject`

Base class. Holds a config, owns a list of `ParticleEmitter`s, and provides
the default draw/update protocol.

```python
class SceneObject:
    def __init__(self, config, loc_model, loc_color): ...

    def build_matrix(self) -> np.ndarray:
        # Builds TRS from self.pos, self.angle, self.scale / self.scale_xyz

    def draw(self):
        # Sets model uniform, dispatches geometry_parts or geometry_range,
        # then draws each emitter.

    def update(self, dt):
        # Calls e.update(dt) for each emitter.
```

`self.pos`, `self.scale`, and `self.angle` start from config but are **mutable**
at runtime — subclasses update them in `update()` to animate.

### Behavior subclasses

#### `BobbingObject(SceneObject)`

Animates `self.pos[1]` with a two-frequency sine wave each frame.
Parameters: `base_y`, `bob_amplitude`, `bob_speed`.

```python
def update(self, dt):
    t = self.bob_speed * state.last_frame
    self.pos[1] = self.base_y + self.bob_amplitude * (
        0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
    )
    super().update(dt)
```

Any floating object (player boat, could add buoys, debris, etc.) inherits this.

---

#### `OrbitalGroup(SceneObject)`

Draws `count` copies of the same mesh evenly around a circle.
Parameters: `count`, `radius`, `center`, `speed`, `facing_offset`.

`facing_offset=0.0` for sharks (fin faces travel direction naturally).
`facing_offset=90.0` for horizon boats (boat mesh needs +90° to face tangent).

```python
def update(self, dt):
    self.orbit_angle += self.speed * dt
    super().update(dt)    # advances emitters

def draw(self):
    for i in range(self.count):
        deg = self.orbit_angle + i * (360.0 / self.count)
        rad = math.radians(deg)
        self.pos[0] = self.center[0] + self.radius * math.sin(rad)
        self.pos[2] = self.center[2] + self.radius * math.cos(rad)
        self.angle  = self.facing_offset + deg
        super().draw()
```

Note: `OrbitalGroup` does **not** own its `orbit_angle` from state — it owns it
internally and updates it via `speed * dt`. The global `state.shark_angle` and
`state.horizon_boat_angle` become **obsolete**; the objects track their own phase.

---

#### `TiltedObject(SceneObject)`

Supports two-rotation matrices: Y-axis yaw + X-axis tilt.
Used for coqueiros, which can't be expressed with the single-rotation `model_matrix()`.

```python
def build_matrix(self) -> np.ndarray:
    # translate → rotate Y (yaw) → rotate X (tilt) → scale
    m = glm.translate(glm.mat4(1.0), glm.vec3(*self.pos))
    m = glm.rotate(m, math.radians(self.angle), glm.vec3(0, 1, 0))
    m = glm.rotate(m, math.radians(self.x_tilt), glm.vec3(1, 0, 0))
    m = glm.scale(m, glm.vec3(self.scale, self.scale, self.scale))
    return np.array(m)

def update(self, dt):
    self.scale = state.coqueiro_scale   # driven by global grow animation
    super().update(dt)
```

Three `TiltedObject` instances replace the `draw_coqueiro()` loop.

---

#### `SpinningSun(SceneObject)`

Overrides `build_matrix()` to apply a fixed tilt (90° around (1,0,1)) followed
by a state-driven Y-spin. Can't use `model_matrix()` for this because it only
supports one rotation.

```python
def build_matrix(self) -> np.ndarray:
    m = glm.translate(glm.mat4(1.0), glm.vec3(*self.pos))
    m = glm.rotate(m, math.radians(SUN_ROT_ANGLE), glm.vec3(*SUN_ROT_AXIS))
    m = glm.rotate(m, math.radians(state.sun_spin), glm.vec3(0, 1, 0))
    m = glm.scale(m, glm.vec3(self.scale, self.scale, self.scale))
    return np.array(m)
```

The fixed tilt constants live in `SpinningSun`, not in `ObjectConfig`, since they
are purely behavioral (they describe how the sun orients itself, not what it looks like).

---

#### `PlayerBoat(BobbingObject)`

Syncs position and heading from `state` each frame, then delegates bobbing and
emitter updates to `BobbingObject`.

```python
def update(self, dt):
    self.pos[0] = state.boat_x
    self.pos[2] = state.boat_z
    self.angle  = state.boat_angle
    super().update(dt)    # applies bob to self.pos[1], updates emitters
```

Particle emitter positions (chimney smoke, bow spray port/starboard) are computed
in `PlayerBoat.update()` using `_local_to_world()`. The two bow spray emitters
have their `active` flag tied to `state.boat_moving_forward` here as well.

The `_local_to_world` helper moves to `objects.py` as a module-level function.

---

## `configs.py`

One `ObjectConfig` per visual identity. The file imports from `geometry` for mesh
refs, but knows nothing about GL or behavior classes.

```python
# configs.py
from . import geometry
from .objects import ObjectConfig

SEA = ObjectConfig(
    scale_xyz=(40.0, 1.0, 50.0),
    default_color=(0.05, 0.35, 0.65, 1.0),
    geometry_range=(geometry.start_sea, geometry.count_sea),
)

ISLAND = ObjectConfig(
    pos=(-7.0, 1.5 * 0.559, -6.0),
    scale=1.5,
    default_color=(0.76, 0.70, 0.50, 1.0),
    geometry_range=(geometry.start_island, geometry.count_island),
)

VOLCANO = ObjectConfig(
    pos=(7.0, 1.363, 5.0),
    default_color=(0.35, 0.30, 0.28, 1.0),
    geometry_range=(geometry.start_volcano, geometry.count_volcano),
)

SUN = ObjectConfig(
    pos=(20.0, 12.0, -15.0),
    scale=2.0,
    default_color=(1.0, 0.85, 0.10, 1.0),
    geometry_range=(geometry.start_sun, geometry.count_sun),
)

LIGHTHOUSE = ObjectConfig(
    pos=(-7.0, 1.5 * 1.416, -6.0),
    scale=0.3,
    geometry_parts=geometry.lh_parts,
    part_colors={
        "lighthouse_body":      (0.980, 0.361, 0.361, 1.0),
        "Cylinder.001":         (0.992, 0.541, 0.420, 1.0),
        "lighthouse_top_floor": (0.996, 0.761, 0.533, 1.0),
        "lighthouse_light":     (0.984, 0.937, 0.463, 1.0),
    },
)

# Coqueiro: three separate TiltedObject instances share this config,
# each overriding pos/angle/x_tilt at construction time.
COQUEIRO = ObjectConfig(
    geometry_parts=geometry.coqueiro_parts,
    part_colors={
        "tronco": (0.42, 0.30, 0.20, 1.0),
        "folhas": (0.18, 0.62, 0.28, 1.0),
    },
)

PLAYER_BOAT = ObjectConfig(
    scale=0.6,
    geometry_parts=geometry.boat_parts,
    part_colors={
        "boat_bottom": (1.000, 0.608, 0.000, 1.0),
        "boat_top":    (0.922, 0.890, 0.537, 1.0),
        "cabin":       (1.000, 0.788, 0.000, 1.0),
        "cabin_top":   (1.000, 0.882, 0.000, 1.0),
        "chimney":     (1.000, 0.608, 0.000, 1.0),
    },
)

HORIZON_BOAT = ObjectConfig(
    scale=0.48,                             # 0.6 * 0.8
    geometry_parts=geometry.boat_parts,     # same mesh as PLAYER_BOAT
    part_colors={
        "boat_bottom": (0.22, 0.22, 0.22, 1.0),
        "boat_top":    (0.30, 0.30, 0.30, 1.0),
        "cabin":       (0.28, 0.28, 0.28, 1.0),
        "cabin_top":   (0.25, 0.25, 0.25, 1.0),
        "chimney":     (0.18, 0.18, 0.18, 1.0),
    },
)

SHARK_FIN = ObjectConfig(
    scale=0.6,
    default_color=(0.25, 0.25, 0.30, 1.0),
    geometry_range=(geometry.start_fin, geometry.count_fin),
)
```

`HORIZON_BOAT` reuses `geometry.boat_parts` with different colors — the same mesh,
a different visual identity. This is the clearest win from the config/behavior split.

---

## `scene.py` after refactor

Assembly becomes wiring:

```python
class Scene:
    def __init__(self, program):
        lm = glGetUniformLocation(program, "model")
        lc = glGetUniformLocation(program, "color")

        self.objects = [
            SceneObject(configs.SEA,        lm, lc),
            SceneObject(configs.ISLAND,     lm, lc),
            SceneObject(configs.VOLCANO,    lm, lc),
            SceneObject(configs.LIGHTHOUSE, lm, lc),
            SpinningSun(configs.SUN,        lm, lc),
            TiltedObject(configs.COQUEIRO,  lm, lc, pos=(-9.300, 1.9984, -6.039), angle=2.3,   x_tilt=0.0),
            TiltedObject(configs.COQUEIRO,  lm, lc, pos=(-6.989, 0.7717, -3.975), angle=27.0,  x_tilt=30.0),
            TiltedObject(configs.COQUEIRO,  lm, lc, pos=(-10.566, 0.839, -5.779), angle=-75.8, x_tilt=30.0),
            PlayerBoat(configs.PLAYER_BOAT, lm, lc, base_y=0.4),
            OrbitalGroup(configs.HORIZON_BOAT, lm, lc, count=3, radius=40.0, speed=2.0,  facing_offset=90.0),
            OrbitalGroup(configs.SHARK_FIN,    lm, lc, count=3, radius=3.0,  speed=25.0, facing_offset=0.0),
        ]

        self.volcano_smoke = ParticleEmitter(...)   # static; not owned by an object

    def update(self, dt):
        for obj in self.objects:
            obj.update(dt)

    def draw_all(self):
        for obj in self.objects:
            obj.draw()
        self.volcano_smoke.update(state.delta_time)
        self.volcano_smoke.draw(self.loc_model, self.loc_color)

    def set_view_projection(self, mat_view, mat_proj): ...
```

Adding a new scene object is one line in `__init__`. No new draw method, no wiring
in `draw_all`.

---

## Edge cases and decisions

### Non-uniform scale (sea)
`ObjectConfig.scale_xyz: tuple | None` overrides uniform `scale` when set.
Only the sea uses this. `SceneObject.build_matrix()`:
```python
sx, sy, sz = self.scale_xyz if self.scale_xyz else (self.scale,) * 3
```

### Sun double-rotation
`SpinningSun` overrides `build_matrix()` entirely. The fixed tilt constants
(`SUN_ROT_ANGLE = 90.0`, `SUN_ROT_AXIS = (1, 0, 1)`) are class-level on
`SpinningSun`, not in `ObjectConfig` — they are behavioral, not visual identity.

### Coqueiro two-rotation
`TiltedObject` overrides `build_matrix()` with translate → rotateY → rotateX → scale.
The `x_tilt` parameter is a constructor arg, not in `ObjectConfig`.
Three instances of `TiltedObject` with the same `COQUEIRO` config and different
per-instance `pos/angle/x_tilt` values.

### OrbitalGroup orbit angle
`OrbitalGroup` owns `self.orbit_angle` internally, updated via `speed * dt`.
The old `state.shark_angle` and `state.horizon_boat_angle` globals become unused
and can be removed from `state.py`.

### OrbitalGroup particle emitters
Each `OrbitalGroup` instance receives its per-copy emitters (e.g. 3 smoke emitters
for 3 horizon boats). In `OrbitalGroup.update()`, after computing each instance's
world position, set `self.emitters[i].base_pos` accordingly.

Because `OrbitalGroup.draw()` iterates instances, and emitters are set during
`update()` (not `draw()`), the emitter count must match the instance count.
Constructor creates `count` emitters and appends them to `self.emitters`.

### PlayerBoat emitters
`PlayerBoat.__init__` creates `boat_smoke`, `bow_port`, `bow_starboard` and appends
them to `self.emitters`. `PlayerBoat.update()` repositions them using
`_local_to_world()`, sets `bow_port.active = state.boat_moving_forward`, then calls
`super().update(dt)` which calls `e.update(dt)` for each.

### Volcano smoke
The volcano smoke emitter is **static** (world pos never changes). It's not owned
by a `SceneObject` because there's no `SceneObject` subclass whose `update()`
would reposition it. It stays as a bare `ParticleEmitter` on `Scene`, as it is today.
If a `StaticEmitterObject` subclass ever made sense, this would migrate into it.

---

## What does NOT change

| Module | Reason |
|---|---|
| `geometry.py` | Clean already. Mesh loading and `model_matrix()` are not the problem. |
| `particles.py` | `ParticleEmitter` is already a well-contained class. |
| `state.py` | Mostly stays. `shark_angle` and `horizon_boat_angle` are removed (owned by objects now). |
| `input.py` | No changes needed. |
| `main_scene.py` | Calls `scene.update(dt)` and `scene.draw_all()` — interface unchanged. |

---

## Migration steps

Each step leaves the program runnable.

1. **Create `src/objects.py`** with `ObjectConfig`, `SceneObject`, `BobbingObject`,
   `OrbitalGroup`, `TiltedObject`, `SpinningSun`, `PlayerBoat`. No imports from
   `scene.py`. Test: import the module, no errors.

2. **Create `src/configs.py`** with all `ObjectConfig` instances. Import and verify
   each config has the correct `geometry_parts` or `geometry_range` reference.

3. **Wire `OrbitalGroup`** for sharks and horizon boats in a scratch test. Verify
   orbit positions and facing match the current output visually.

4. **Wire `PlayerBoat`** with smoke and spray emitters. Verify bobbing, smoke, and
   spray match current behavior.

5. **Replace `scene.py`** — swap the per-draw-function structure for the `self.objects`
   list. Keep `set_view_projection` and `volcano_smoke` as-is.

6. **Remove dead code** from `state.py` (`shark_angle`, `horizon_boat_angle`) and
   from `input.py` (any code that updated those globals).
