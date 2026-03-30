import glfw
from OpenGL.GL import *
import numpy as np
import glm
import ctypes
from shader_s import Shader

import state
import geometry
import input as inp
from scene import Scene


# ─── Window ───────────────────────────────────────────────────────────────────

glfw.init()
glfw.window_hint(glfw.VISIBLE, glfw.FALSE)

window = glfw.create_window(state.WIDTH, state.HEIGHT, "Ocean Scene", None, None)
if not window:
    glfw.terminate()
    raise RuntimeError("Failed to create GLFW window")

glfw.make_context_current(window)


# ─── Shaders ──────────────────────────────────────────────────────────────────

ourShader = Shader("vertex_shader.vs", "fragment_shader.fs")
ourShader.use()
program = ourShader.getProgram()


# ─── Upload geometry to GPU ───────────────────────────────────────────────────
# geometry.py populated vertices_list at import time.

vertices = np.zeros(len(geometry.vertices_list), [("position", np.float32, 3)])
vertices["position"] = geometry.vertices_list

vbo = glGenBuffers(1)
glBindBuffer(GL_ARRAY_BUFFER, vbo)
glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

stride = vertices.strides[0]
loc_position = glGetAttribLocation(program, "position")
glEnableVertexAttribArray(loc_position)
glVertexAttribPointer(loc_position, 3, GL_FLOAT, False, stride, ctypes.c_void_p(0))


# ─── Scene ────────────────────────────────────────────────────────────────────

scene = Scene(program)


# ─── Input callbacks ──────────────────────────────────────────────────────────

glfw.set_key_callback(window, inp.key_event)
glfw.set_cursor_pos_callback(window, inp.mouse_callback)
glfw.set_scroll_callback(window, inp.scroll_callback)

if state.FREE_CAMERA:
    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)


# ─── Render loop ──────────────────────────────────────────────────────────────

glfw.show_window(window)
glEnable(GL_DEPTH_TEST)

if state.FREE_CAMERA:
    print("\nFree camera ON  –  WASD move · Mouse look · Scroll zoom · C snapshot · P wireframe · ESC quit\n")
else:
    print("\nStatic camera  –  P wireframe · ESC quit  (set FREE_CAMERA=True in state.py to re-enable fly mode)\n")

while not glfw.window_should_close(window):
    now = glfw.get_time()
    state.delta_time = now - state.last_frame
    state.last_frame = now

    glfw.poll_events()
    inp.process_boat()
    state.shark_angle += scene.SHARK_SPEED  * state.delta_time
    state.sun_spin    += state.SUN_SPIN_SPEED * state.delta_time

    glClearColor(0.53, 0.81, 0.98, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if state.wireframe else GL_FILL)

    if state.FREE_CAMERA:
        mat_view = np.array(glm.lookAt(state.cam_pos, state.cam_pos + state.cam_front, state.cam_up))
        mat_proj = np.array(glm.perspective(glm.radians(state.fov), state.WIDTH / state.HEIGHT, 0.1, 200.0))
    else:
        mat_view = state.mat_view_static
        mat_proj = state.mat_proj_static

    scene.set_view_projection(mat_view, mat_proj)
    scene.draw_all()

    glfw.swap_buffers(window)

glfw.terminate()
