"""Input handling: key callbacks and per-frame processing.

Object bindings
---------------
Call set_target(boat) and set_coqueiros(trees) once after the scene is
constructed (see main_scene.py).  Until then, process_boat and
process_coqueiro_scale fall back to writing state.boat_* and
state.coqueiro_scale so the program remains fully functional during the
transition — the legacy paths are removed in the final wiring PR.

Constants
---------
Behavior constants that were previously in state.py live here alongside the
code that uses them.  They are not application state — they are parameters.
"""

import math

import glfw

from . import state

# ---------------------------------------------------------------------------
# Constants (moved from state.py)
# ---------------------------------------------------------------------------

BOAT_SPEED = 2.0  # world units per second
BOAT_ROT = 45.0  # degrees per second

COQUEIRO_SCALE_MIN = 0.01
COQUEIRO_SCALE_MAX = 0.15
COQUEIRO_SCALE_SPEED = 0.18  # scale units per second

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

keys_pressed: set = set()  # currently held glfw key codes; moved from state.py

_target = None   # PlayerBoat reference; set via set_target()
_coqueiros = []  # list of coqueiro SceneObjects; set via set_coqueiros()


# ---------------------------------------------------------------------------
# Binding functions
# ---------------------------------------------------------------------------


def set_target(boat) -> None:
    """Bind the PlayerBoat that process_boat() will drive.

    Call once in main_scene.py after the scene is constructed:
        inp.set_target(scene.get_player_boat())

    Until called, process_boat() uses the legacy state.boat_* path so the
    program keeps running.
    """
    global _target
    _target = boat


def set_coqueiros(trees) -> None:
    """Bind the list of coqueiro SceneObjects that process_coqueiro_scale() will drive.

    Call once in main_scene.py after the scene is constructed:
        inp.set_coqueiros(scene.get_coqueiros())

    Until called, process_coqueiro_scale() uses the legacy state.coqueiro_scale
    path so the program keeps running.
    """
    global _coqueiros
    _coqueiros = list(trees)


# ---------------------------------------------------------------------------
# GLFW callback
# ---------------------------------------------------------------------------


def key_event(window, key, scancode, action, mods) -> None:
    if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
        glfw.set_window_should_close(window, True)

    if key == glfw.KEY_P and action == glfw.PRESS:
        state.wireframe = not state.wireframe  # removed in final wiring PR

    if action == glfw.PRESS:
        keys_pressed.add(key)
    elif action == glfw.RELEASE:
        keys_pressed.discard(key)


# ---------------------------------------------------------------------------
# Per-frame processors
# ---------------------------------------------------------------------------


def process_boat(dt: float) -> None:
    """Update boat position and heading from held keys.

    New path (after set_target is called): writes directly to
    _target.transform — no shared globals.

    Legacy path (before set_target is called): writes to state.boat_* so
    the program runs correctly during the transition.  Removed in the final
    wiring PR once set_target() is called at startup.
    """
    if _target is None:
        # Legacy path — mirrors original behavior using moved constants
        if glfw.KEY_A in keys_pressed:
            state.boat_angle += BOAT_ROT * dt
        if glfw.KEY_D in keys_pressed:
            state.boat_angle -= BOAT_ROT * dt
        state.boat_moving_forward = glfw.KEY_W in keys_pressed
        if glfw.KEY_W in keys_pressed or glfw.KEY_S in keys_pressed:
            dx = math.sin(math.radians(state.boat_angle))
            dz = math.cos(math.radians(state.boat_angle))
            if glfw.KEY_W in keys_pressed:
                state.boat_x += dx * BOAT_SPEED * dt
                state.boat_z += dz * BOAT_SPEED * dt
            if glfw.KEY_S in keys_pressed:
                state.boat_x -= dx * BOAT_SPEED * dt
                state.boat_z -= dz * BOAT_SPEED * dt
        return

    # New path: write directly to the boat's transform
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


def process_coqueiro_scale(dt: float) -> None:
    """Scale all coqueiros up (Z) or down (X), clamped to [MIN, MAX].

    New path (after set_coqueiros is called): writes directly to each
    tree's transform.scale.

    Legacy path (before set_coqueiros is called): writes to
    state.coqueiro_scale so the program runs correctly during the transition.
    Removed in the final wiring PR once set_coqueiros() is called at startup.
    """
    sp = COQUEIRO_SCALE_SPEED * dt

    if _coqueiros:
        # New path: write directly to each tree's transform
        if glfw.KEY_Z in keys_pressed:
            for tree in _coqueiros:
                tree.transform.scale = min(
                    COQUEIRO_SCALE_MAX, tree.transform.scale + sp
                )
        if glfw.KEY_X in keys_pressed:
            for tree in _coqueiros:
                tree.transform.scale = max(
                    COQUEIRO_SCALE_MIN, tree.transform.scale - sp
                )
    else:
        # Legacy path — writes to state until set_coqueiros() is called
        if glfw.KEY_Z in keys_pressed:
            state.coqueiro_scale = min(
                COQUEIRO_SCALE_MAX, state.coqueiro_scale + sp
            )
        if glfw.KEY_X in keys_pressed:
            state.coqueiro_scale = max(
                COQUEIRO_SCALE_MIN, state.coqueiro_scale - sp
            )
