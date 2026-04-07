import glfw
from OpenGL.GL import *
import numpy as np
import ctypes
from src.shader_s import Shader

from src import state
from src import geometry
from src import input as inp
from src.scene import Scene


# Window

glfw.init()
glfw.window_hint(glfw.VISIBLE, glfw.FALSE)

window = glfw.create_window(state.WIDTH, state.HEIGHT, "Ocean Scene", None, None)
if not window:
    glfw.terminate()
    raise RuntimeError("Failed to create GLFW window")

glfw.make_context_current(window)


# Shaders

ourShader = Shader("shaders/vertex_shader.vs", "shaders/fragment_shader.fs")
ourShader.use()
program = ourShader.getProgram()


# Upload geometry to GPU
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


# Scene

scene = Scene(program)


# Input callbacks

glfw.set_key_callback(window, inp.key_event)

# Render loop

glfw.show_window(window)
glEnable(GL_DEPTH_TEST)

print("\nW/S move · A/D rotate boat · Z/X coqueiro scale · P wireframe · ESC quit\n")

while not glfw.window_should_close(window):
    now = glfw.get_time()
    state.delta_time = now - state.last_frame
    state.last_frame = now

    glfw.poll_events()
    inp.process_coqueiro_scale()
    inp.process_boat()
    state.shark_angle        += scene.SHARK_SPEED        * state.delta_time
    state.horizon_boat_angle += scene.HORIZON_BOAT_SPEED * state.delta_time
    state.sun_spin           += state.SUN_SPIN_SPEED     * state.delta_time

    glClearColor(0.53, 0.81, 0.98, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if state.wireframe else GL_FILL)

    scene.set_view_projection(state.mat_view_static, state.mat_proj_static)
    scene.draw_all()

    glfw.swap_buffers(window)

glfw.terminate()
