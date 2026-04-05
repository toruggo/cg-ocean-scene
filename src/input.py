import glfw
import math

from . import state


def key_event(window, key, scancode, action, mods):
    if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
        glfw.set_window_should_close(window, True)

    if key == glfw.KEY_P and action == glfw.PRESS:
        state.wireframe = not state.wireframe

    # Track held keys for boat and scale movement
    if action == glfw.PRESS:
        state.keys_pressed.add(key)
    elif action == glfw.RELEASE:
        state.keys_pressed.discard(key)


def mouse_callback(window, xpos, ypos):
    pass


def scroll_callback(window, xoffset, yoffset):
    pass


def process_coqueiro_scale():
    """A increases scale, Z decreases (clamped by state limits)."""
    if state.delta_time <= 0.0:
        return
    sp = state.COQUEIRO_SCALE_SPEED * state.delta_time
    if glfw.KEY_Z in state.keys_pressed:
        state.coqueiro_scale = min(state.COQUEIRO_SCALE_MAX, state.coqueiro_scale + sp)
    if glfw.KEY_X in state.keys_pressed:
        state.coqueiro_scale = max(state.COQUEIRO_SCALE_MIN, state.coqueiro_scale - sp)


def process_boat():
    """Called every frame. Reads keys_pressed and updates boat state."""
    if glfw.KEY_A in state.keys_pressed:
        state.boat_angle += state.BOAT_ROT * state.delta_time   # CCW = left
    if glfw.KEY_D in state.keys_pressed:
        state.boat_angle -= state.BOAT_ROT * state.delta_time   # CW  = right

    state.boat_moving_forward = glfw.KEY_W in state.keys_pressed

    if glfw.KEY_W in state.keys_pressed or glfw.KEY_S in state.keys_pressed:
        dx = math.sin(math.radians(state.boat_angle))
        dz = math.cos(math.radians(state.boat_angle))
        if glfw.KEY_W in state.keys_pressed:
            state.boat_x += dx * state.BOAT_SPEED * state.delta_time
            state.boat_z += dz * state.BOAT_SPEED * state.delta_time
        if glfw.KEY_S in state.keys_pressed:
            state.boat_x -= dx * state.BOAT_SPEED * state.delta_time
            state.boat_z -= dz * state.BOAT_SPEED * state.delta_time
