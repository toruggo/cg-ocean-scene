# Refactoring Plan

Each PR is independently reviewable, leaves the program runnable, and has a
single reason to exist. PRs 1–4 are pure additions — no existing code changes,
zero runtime risk. PRs 5–9 modify live code, in increasing order of blast
radius. The final PR deletes `state.py`.

---

## PR 1 — `particles.py`: add `anchor` field

**Branch:** `refactor/particle-anchor`  
**Files:** `src/particles.py` (+1 line)  
**Depends on:** nothing

### Change

```python
# In ParticleEmitter.__init__, alongside other instance attributes:
self.anchor = None   # local-space offset; set by owner when needed
```

### Why

Every subsequent PR that attaches a smoke emitter to a moving object
(chimney smoke, bow spray) depends on this field. Doing it first and alone
keeps the diff trivially reviewable.

### Verify

Program runs identically. No behavior changes — `anchor` is `None` everywhere
and `SceneObject.update()` doesn't exist yet to read it.

---

## PR 2 — `app.py`: introduce `AppState`

**Branch:** `refactor/app-state`  
**Files:** `src/app.py` (new file)  
**Depends on:** nothing

### Change

New file only. No existing code modified.

```python
# src/app.py
from dataclasses import dataclass

@dataclass
class AppState:
    width:     int  = 960
    height:    int  = 720
    wireframe: bool = False
```

### Why

`AppState` needs to exist before `main_scene.py` and `scene.py` are wired.
Creating it early with no consumers keeps the PR minimal and harmless.

### Verify

Program runs identically. Nothing imports `app.py` yet.

---

## PR 3 — `objects.py`: all core abstractions

**Branch:** `refactor/objects`  
**Files:** `src/objects.py` (new file)  
**Depends on:** PR 1 (`ParticleEmitter.anchor`)

### Change

New file only. No existing code modified. Contains, in order:

1. `Drawable` Protocol (`update(dt)` / `draw()`)
2. `Transform` dataclass with composable `rotations` list and explicit `heading`
3. `ObjectConfig` dataclass — visual identity only, no transform fields
4. `_local_to_world(anchor, scale, heading, tx, ty, tz)` helper
5. `_make_emitter(anchor, **kwargs)` helper
6. `SceneObject` base — `init_gl` classmethod, `draw()`, `update()` with
   anchor-aware emitter loop
7. `BobbingObject(SceneObject)` — accumulated `_time`, two-frequency sine bob
8. `SpinningSun(SceneObject)` — owns `_spin`, no longer reads `state.sun_spin`
9. `PlayerBoat(BobbingObject)` — chimney smoke + bow spray, reads own
   `moving_forward` attribute (set by `input.py`)
10. `OrbitalGroup` — container of N `SceneObject` instances, owns
    `orbit_angle`, accepts `make_emitter` factory
11. Boat constants (`CHIMNEY_TOP_LOCAL`, `BOW_LOCAL`, `BOW_SPRAY_SPEED`,
    `BOW_BACKWARD_SPEED`)

### Why

All classes in one file means the module has no internal circular imports.
Nothing in `objects.py` references `state.py`, `scene.py`, or `input.py`.
The reviewer can read the file end-to-end without context-switching.

### Verify

`python -c "from src.objects import SceneObject, OrbitalGroup, PlayerBoat"`
succeeds. Program still runs identically — nothing wires these classes yet.

---

## PR 4 — `configs.py`: visual identity catalog

**Branch:** `refactor/configs`  
**Files:** `src/configs.py` (new file)  
**Depends on:** PR 3 (`ObjectConfig`)

### Change

New file only. No existing code modified. One `ObjectConfig` per visual
identity: `SEA`, `ISLAND`, `VOLCANO`, `SUN`, `LIGHTHOUSE`, `COQUEIRO`,
`PLAYER_BOAT`, `HORIZON_BOAT`, `SHARK_FIN`.

Imports only from `objects.py` and `geometry.py` — no circular risk.

### Why

Separating the catalog into its own file makes the reviewer's job easy:
every config is just a data declaration, trivially cross-checkable against
the existing hard-coded colors in `scene.py`.

### Verify

`python -c "from src import configs"` succeeds. Program still runs identically.

---

## PR 5 — `input.py`: decouple from `state.py`

**Branch:** `refactor/input-decouple`  
**Files:** `src/input.py` (modify)  
**Depends on:** PR 3 (`PlayerBoat`, `Transform`)

### Change

- Move `keys_pressed` from `state.py` into `input.py` as a module-level set.
- Move `BOAT_SPEED`, `BOAT_ROT`, `COQUEIRO_SCALE_MIN/MAX/SPEED` from
  `state.py` into `input.py`.
- Add `_target = None` and `set_target(boat)`.
- Add `_coqueiros = []` and `set_coqueiros(trees)`.
- Rewrite `process_boat(dt)` to write to `_target.transform` (heading,
  rotations, pos, moving_forward) instead of `state.boat_*`.
- Rewrite `process_coqueiro_scale(dt)` to iterate `_coqueiros` and write to
  `tree.transform.scale` instead of `app.coqueiro_scale`.

`state.py` imports can stay in `input.py` temporarily (wireframe toggle still
reads `state.wireframe`). They disappear in PR 9.

### What the diff looks like

- ~10 lines added at top (constants + module state)
- `set_target` and `set_coqueiros` are new functions (~8 lines each)
- `process_boat`: same logic, different write target (`_target.transform.*`
  instead of `state.boat_*`)
- `process_coqueiro_scale`: `app` parameter removed, loop over `_coqueiros`

### Verify

`set_target` and `set_coqueiros` are not called yet — `process_boat` and
`process_coqueiro_scale` have no-op guards (`if _target is None: return`).
Program runs identically; boat still moves because `main_scene.py` still
calls the old code path.

> **Note:** Until PR 9 wires `set_target` and `set_coqueiros`, the new
> functions are dead code. That is intentional — this PR's job is to make
> the new functions exist and correct, not to activate them.

---

## PR 6 — `scene.py`: replace static objects

**Branch:** `refactor/scene-static`  
**Files:** `src/scene.py` (modify)  
**Depends on:** PRs 3, 4 (`objects.py`, `configs.py`)

### Change

Replace the individual draw functions for non-moving objects with a
`self.objects` list containing `SceneObject` and `SpinningSun` instances:

- `SEA`, `ISLAND`, `LIGHTHOUSE` → `SceneObject(configs.X, Transform(...))`
- Coqueiros → `SceneObject(configs.COQUEIRO, t)` per transform; stored in
  `self._coqueiros`; expanded into `self.objects`
- `VOLCANO` → `SceneObject` with `ParticleEmitter` appended (smoke attached
  to the object, not orphaned in Scene)
- `SUN` → `SpinningSun(configs.SUN, Transform(...))` (owns its own `_spin`;
  `state.sun_spin` is no longer read)
- Camera matrices move from `state.py` into `Scene.__init__`
- `set_view_projection` uses `SceneObject.loc_view` / `loc_projection`
- `update(dt)` and `draw_all()` loop over `self.objects`

Old draw functions for these objects are **removed** in the same PR — no
hybrid state.

The orbital groups (sharks, horizon boats) and `PlayerBoat` still use the
old draw functions; those are replaced in PRs 7 and 8.

### Verify

All static objects visible, correctly positioned and colored. Volcano smoke
rises. Sun spins. Coqueiro tilt is correct. Camera angle unchanged.

---

## PR 7 — `scene.py`: replace orbital objects

**Branch:** `refactor/scene-orbitals`  
**Files:** `src/scene.py` (modify)  
**Depends on:** PR 6 (Scene now has `self.objects`)

### Change

Replace the old orbit-draw loops for sharks and horizon boats with two
`OrbitalGroup` instances appended to `self.objects`:

```python
OrbitalGroup(configs.HORIZON_BOAT, count=3, radius=40.0, speed=2.0,
             facing_offset=90.0,
             make_emitter=lambda: _make_emitter(
                 anchor=CHIMNEY_TOP_LOCAL,
                 color=(0.60, 0.60, 0.65, 1.0), ...
             )),
OrbitalGroup(configs.SHARK_FIN, count=3, radius=3.0, speed=25.0,
             facing_offset=0.0,
             make_emitter=lambda: _make_emitter(
                 anchor=(0.0, 0.0, 0.0),
                 color=(0.75, 0.88, 1.0, 1.0), ...
             )),
```

`state.shark_angle` and `state.horizon_boat_angle` are no longer read.
Old orbit draw functions (`_orbit_instances` calls) are removed in the same PR.

### Verify

Three sharks orbit correctly at radius 3.0, facing direction matches old
behavior. Three horizon boats orbit at radius 40.0, facing 90° offset. All
six have visible emitter smoke/trail. Orbit speed matches original.

---

## PR 8 — `scene.py`: replace `PlayerBoat`

**Branch:** `refactor/scene-player-boat`  
**Files:** `src/scene.py` (modify)  
**Depends on:** PRs 5 (input decouple), 7 (orbitals already in `self.objects`)

### Change

Replace the old player boat draw function with a `PlayerBoat` instance in
`self.objects`:

```python
PlayerBoat(configs.PLAYER_BOAT, Transform(scale=0.6), base_y=0.4),
```

Add `get_player_boat()` and `get_coqueiros()` accessors to `Scene`.

`update(dt)` replaces `update(dt, app)` — `app` parameter removed, coqueiro
scale loop removed (handled by `input.py` since PR 5).

Old player boat draw function removed. `state.boat_x/z/angle` and
`state.boat_moving_forward` are no longer read by `scene.py`.

### Verify

Boat bobs on water. Chimney smoke rises from chimney position. Bow spray
appears when moving forward. W/A/S/D movement and rotation work correctly.

> **Note:** W/A/S/D will stop working until PR 9 calls `inp.set_target()`.
> This is acceptable during the review window — the PR author verifies
> locally by temporarily patching the wiring, then PR 9 makes it permanent.
> Alternatively, add a temporary `set_target` call in `__init__` as a
> scaffold, removed in PR 9.

---

## PR 9 — wire `main_scene.py` + delete `state.py`

**Branch:** `refactor/wire-and-delete-state`  
**Files:** `src/main_scene.py` (modify), `src/state.py` (delete),
           `src/input.py` (remove remaining `state.*` references)  
**Depends on:** PRs 2, 5, 8 (AppState, input bindings, full scene assembled)

### Change

**`main_scene.py`:**
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

**`input.py`:** Remove remaining `state.*` references (wireframe toggle now
reads `app.wireframe` via a `set_app(app)` binding or a passed reference).

**`state.py`:** Deleted. `git grep "from.*state import\|import.*state"` should
return empty before this PR merges.

### Verify

Full smoke test: boat moves/rotates, coqueiros scale with Z/X, sharks and
horizon boats orbit, volcano smoke, sun spins, wireframe toggle works.
No `ImportError` or `AttributeError` from old `state` references.

---

## Summary

| PR | Branch | Files | Risk | Runnable after merge |
|---|---|---|---|---|
| 1 | `refactor/particle-anchor` | `particles.py` +1 line | None | Yes |
| 2 | `refactor/app-state` | `app.py` new | None | Yes |
| 3 | `refactor/objects` | `objects.py` new | None | Yes |
| 4 | `refactor/configs` | `configs.py` new | None | Yes |
| 5 | `refactor/input-decouple` | `input.py` modify | Low | Yes (new fns are dead code) |
| 6 | `refactor/scene-static` | `scene.py` modify | Medium | Yes |
| 7 | `refactor/scene-orbitals` | `scene.py` modify | Medium | Yes |
| 8 | `refactor/scene-player-boat` | `scene.py` modify | Medium | Yes* |
| 9 | `refactor/wire-and-delete-state` | `main_scene.py` modify, `state.py` delete | Medium | Yes |

\* boat input broken until PR 9; see note in PR 8.

## Dependency graph

```
PR 1 ──────────────────────────────────────────────────┐
PR 2 ──────────────────────────────────────────────┐   │
PR 3 (needs PR 1) ──────────┬──────────────┐       │   │
PR 4 (needs PR 3) ──────────┤              │       │   │
PR 5 (needs PR 3) ──────────┤              │       │   │
PR 6 (needs PR 3, 4) ───────┤              │       │   │
PR 7 (needs PR 6) ──────────┤              │       │   │
PR 8 (needs PR 5, 7) ───────┤              │       │   │
PR 9 (needs PR 2, 5, 8) ────┘              └───────┴───┘
```
