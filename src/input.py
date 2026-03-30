import glfw
import glm
import math

from . import state


def key_event(window, key, scancode, action, mods):
    if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
        glfw.set_window_should_close(window, True)

    if key == glfw.KEY_P and action == glfw.PRESS:
        state.wireframe = not state.wireframe

    # Track held keys for boat movement (and free-camera movement)
    if action == glfw.PRESS:
        state.keys_pressed.add(key)
    elif action == glfw.RELEASE:
        state.keys_pressed.discard(key)

    if not state.FREE_CAMERA:
        return

    # ── Free-camera controls ──────────────────────────────────────────────────
    if key == glfw.KEY_C and action == glfw.PRESS:
        target = state.cam_pos + state.cam_front
        print("\n── Camera snapshot ──────────────────────────")
        print(f"  cameraPos    = glm.vec3({state.cam_pos.x:.4f}, {state.cam_pos.y:.4f}, {state.cam_pos.z:.4f})")
        print(f"  cameraTarget = glm.vec3({target.x:.4f}, {target.y:.4f}, {target.z:.4f})")
        print(f"  cameraUp     = glm.vec3({state.cam_up.x:.4f}, {state.cam_up.y:.4f}, {state.cam_up.z:.4f})")
        print(f"  fov          = {state.fov:.1f}")
        print("─────────────────────────────────────────────\n")

    speed = 10.0 * state.delta_time
    if key == glfw.KEY_W and action in (glfw.PRESS, glfw.REPEAT):
        state.cam_pos += speed * state.cam_front
    if key == glfw.KEY_S and action in (glfw.PRESS, glfw.REPEAT):
        state.cam_pos -= speed * state.cam_front
    if key == glfw.KEY_A and action in (glfw.PRESS, glfw.REPEAT):
        state.cam_pos -= glm.normalize(glm.cross(state.cam_front, state.cam_up)) * speed
    if key == glfw.KEY_D and action in (glfw.PRESS, glfw.REPEAT):
        state.cam_pos += glm.normalize(glm.cross(state.cam_front, state.cam_up)) * speed


def mouse_callback(window, xpos, ypos):
    if not state.FREE_CAMERA:
        return

    if state.first_mouse:
        state.last_x = xpos
        state.last_y = ypos
        state.first_mouse = False

    xoffset = (xpos - state.last_x) * 0.1
    yoffset = (state.last_y - ypos) * 0.1
    state.last_x = xpos
    state.last_y = ypos

    state.yaw  += xoffset
    state.pitch = max(-89.0, min(89.0, state.pitch + yoffset))

    front = glm.vec3(
        math.cos(math.radians(state.yaw)) * math.cos(math.radians(state.pitch)),
        math.sin(math.radians(state.pitch)),
        math.sin(math.radians(state.yaw)) * math.cos(math.radians(state.pitch)),
    )
    state.cam_front = glm.normalize(front)


def scroll_callback(window, xoffset, yoffset):
    if not state.FREE_CAMERA:
        return
    state.fov = max(10.0, min(90.0, state.fov - yoffset))


def process_boat():
    """Called every frame. Reads keys_pressed and updates boat state."""
    if state.FREE_CAMERA:
        return  # WASD is used by free camera in that mode

    if glfw.KEY_A in state.keys_pressed:
        state.boat_angle += state.BOAT_ROT * state.delta_time   # CCW = left
    if glfw.KEY_D in state.keys_pressed:
        state.boat_angle -= state.BOAT_ROT * state.delta_time   # CW  = right

    if glfw.KEY_W in state.keys_pressed or glfw.KEY_S in state.keys_pressed:
        # R_Y(boat_angle) * (0,0,1) = (sin θ, 0, cos θ)
        dx = math.sin(math.radians(state.boat_angle))
        dz = math.cos(math.radians(state.boat_angle))
        if glfw.KEY_W in state.keys_pressed:
            state.boat_x += dx * state.BOAT_SPEED * state.delta_time
            state.boat_z += dz * state.BOAT_SPEED * state.delta_time
        if glfw.KEY_S in state.keys_pressed:
            state.boat_x -= dx * state.BOAT_SPEED * state.delta_time
            state.boat_z -= dz * state.BOAT_SPEED * state.delta_time
