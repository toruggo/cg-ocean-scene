import glfw
from OpenGL.GL import *
import numpy as np
import glm
import math
import ctypes
from shader_s import Shader


# ─── Toggle: set True to re-enable free camera (WASD + mouse) ─────────────────
FREE_CAMERA = False 


# ─── Window ───────────────────────────────────────────────────────────────────

glfw.init()
glfw.window_hint(glfw.VISIBLE, glfw.FALSE)

WIDTH, HEIGHT = 800, 600
window = glfw.create_window(WIDTH, HEIGHT, "Ocean Scene", None, None)
if not window:
    glfw.terminate()
    raise RuntimeError("Failed to create GLFW window")

glfw.make_context_current(window)


# ─── Shaders ──────────────────────────────────────────────────────────────────

ourShader = Shader("vertex_shader.vs", "fragment_shader.fs")
ourShader.use()
program = ourShader.getProgram()


# ─── Geometry helpers ─────────────────────────────────────────────────────────

vertices_list = []


def load_model_from_file(filename):
    vertices = []
    texture_coords = []
    faces = []
    for line in open(filename, "r"):
        if line.startswith('#'):
            continue
        values = line.split()
        if not values:
            continue
        if values[0] == 'v':
            vertices.append(values[1:4])
        elif values[0] == 'vt':
            texture_coords.append(values[1:3])
        elif values[0] == 'f':
            face = []
            face_texture = []
            for v in values[1:]:
                w = v.split('/')
                face.append(int(w[0]))
                face_texture.append(int(w[1]) if len(w) >= 2 and w[1] else 0)
            faces.append((face, face_texture, None))
    return {'vertices': vertices, 'texture': texture_coords, 'faces': faces}


def circular_sliding_window_of_three(arr):
    if len(arr) == 3:
        return arr
    circular_arr = arr + [arr[0]]
    result = []
    for i in range(len(circular_arr) - 2):
        result.extend(circular_arr[i:i + 3])
    return result


def load_obj(filename):
    global vertices_list
    modelo = load_model_from_file(filename)
    start = len(vertices_list)
    for face in modelo['faces']:
        for vid in circular_sliding_window_of_three(face[0]):
            vertices_list.append(modelo['vertices'][vid - 1])
    return start, len(vertices_list) - start


def make_sun(R_inner=1.0, R_outer=1.7, N=12):
    """
    2D sun: dodecagon body + one outward triangle per edge (rays).
    Built flat on the XZ plane, centered at origin.

    Geometry breakdown (N=12):
      - Body : 12 triangles  (center fan over the dodecagon)
      - Rays : 12 triangles  (one spike per edge, apex at midpoint angle)
    Total: 24 triangles, 72 vertices.
    """
    global vertices_list
    start = len(vertices_list)
    step = 2 * math.pi / N

    rim = [(math.cos(i * step), math.sin(i * step)) for i in range(N)]

    # Dodecagon body — fan from center
    for i in range(N):
        cx, cz = rim[i]
        nx, nz = rim[(i + 1) % N]
        vertices_list.append([0.0,           0.0, 0.0          ])
        vertices_list.append([R_inner * cx,  0.0, R_inner * cz ])
        vertices_list.append([R_inner * nx,  0.0, R_inner * nz ])

    # Rays — triangle rooted on each edge, apex points outward
    for i in range(N):
        cx, cz = rim[i]
        nx, nz = rim[(i + 1) % N]
        mid_a  = (i + 0.5) * step
        apex_x = R_outer * math.cos(mid_a)
        apex_z = R_outer * math.sin(mid_a)
        vertices_list.append([R_inner * cx,  0.0, R_inner * cz ])
        vertices_list.append([R_inner * nx,  0.0, R_inner * nz ])
        vertices_list.append([apex_x,        0.0, apex_z       ])

    return start, len(vertices_list) - start


def make_shark_fin():
    """
    Single shark fin in the XY plane, base centered at local origin.
    Two triangles: main body + back-swept notch.

         tip
          *
         /|
        / |
       /  * notch
      /  /
     *--*
    front back
    """
    global vertices_list
    start = len(vertices_list)

    p_front = [-0.20, 0.00, 0.0]
    p_back  = [ 0.30, 0.00, 0.0]
    p_tip   = [ 0.05, 0.80, 0.0]
    p_notch = [ 0.30, 0.28, 0.0]

    # Main body
    vertices_list.append(p_front)
    vertices_list.append(p_back)
    vertices_list.append(p_tip)
    # Back-swept notch
    vertices_list.append(p_back)
    vertices_list.append(p_notch)
    vertices_list.append(p_tip)

    return start, len(vertices_list) - start


def make_cloud(seed, a=2.5, b=1.4, n_circles=12, r_min=0.3, r_max=0.8, N=16, y=0.05):
    """
    Cloud built from overlapping circles distributed inside an ellipse (a × b).

    - Centers are sampled randomly inside the ellipse with a fixed seed
      so the shape is always the same across runs.
    - Circle radius lerps from r_max at the ellipse center to r_min at
      the boundary, giving a puffy middle and ragged edges.
    - Each circle is a triangle fan with N slices.
    - Geometry is in local space (origin = cloud center); use the model
      matrix to place it in the world.
    """
    global vertices_list
    rng   = np.random.default_rng(seed)
    start = len(vertices_list)
    step  = 2 * math.pi / N

    centers = []
    attempts = 0
    while len(centers) < n_circles and attempts < n_circles * 20:
        x = rng.uniform(-a, a)
        z = rng.uniform(-b, b)
        if (x / a) ** 2 + (z / b) ** 2 <= 1.0:
            centers.append((x, z))
        attempts += 1

    for (cx, cz) in centers:
        # Normalised distance from ellipse center (0 = center, 1 = edge)
        dist = math.sqrt((cx / a) ** 2 + (cz / b) ** 2)
        r    = r_max + (r_min - r_max) * dist   # lerp: big in middle, small at edge

        for i in range(N):
            a1 = i * step
            a2 = (i + 1) * step
            vertices_list.append([cx,                        y, cz                       ])
            vertices_list.append([cx + r * math.cos(a1),    y, cz + r * math.sin(a1)    ])
            vertices_list.append([cx + r * math.cos(a2),    y, cz + r * math.sin(a2)    ])

    return start, len(vertices_list) - start


def make_sea_circle(radius=1.0, N=64):
    """
    Filled circle on the XZ plane as a triangle fan, centered at origin.
    Scale sx/sz in the model matrix to turn it into an ellipse.
    """
    global vertices_list
    start = len(vertices_list)
    step = 2 * math.pi / N
    for i in range(N):
        a1 = i * step
        a2 = (i + 1) * step
        vertices_list.append([0.0,                      0.0, 0.0                     ])
        vertices_list.append([radius * math.cos(a1),    0.0, radius * math.sin(a1)   ])
        vertices_list.append([radius * math.cos(a2),    0.0, radius * math.sin(a2)   ])
    return start, len(vertices_list) - start


# ─── Load objects ─────────────────────────────────────────────────────────────

start_boat,     count_boat     = load_obj('barco.obj')
start_island,   count_island   = load_obj('island1.obj')
start_lh,       count_lh       = load_obj('lighthouse.obj')
start_volcano,  count_volcano  = load_obj('volcano_rock.obj')
start_sun,      count_sun      = make_sun(R_inner=.8, R_outer=1.5, N=12)
start_fin,      count_fin      = make_shark_fin()
start_sea,      count_sea      = make_sea_circle(radius=1.0, N=64)

# Each entry: (seed, world_x, world_y, world_z, ellipse_a, ellipse_b, n_circles)
# Tweak world_x/y/z to reposition; change seed for a different cloud shape.
CLOUD_DEFS = [
    (11,  10.0, 12,  -20.0,  3, 1.5, 100),
    # (37,   -8.0, 6.0, -11.0,  2.2, 1.2, 30),
    # (82,  -6.0, 4.5,  -8.0,  1.8, 1.0, 30),
]

clouds = []   # list of (start, count) — indexed same as CLOUD_DEFS
for (seed, *_rest) in CLOUD_DEFS:
    a, b, n = _rest[3], _rest[4], _rest[5]
    s, c = make_cloud(seed=seed, a=a, b=b, n_circles=n)
    clouds.append((s, c))

print(f"Boat      : start={start_boat}     count={count_boat}")
print(f"Island    : start={start_island}   count={count_island}")
print(f"Lighthouse: start={start_lh}       count={count_lh}")
print(f"Volcano   : start={start_volcano}  count={count_volcano}")
print(f"Sun       : start={start_sun}      count={count_sun}")
print(f"Sea       : start={start_sea}      count={count_sea}")


# ─── Upload to GPU ────────────────────────────────────────────────────────────

vertices = np.zeros(len(vertices_list), [("position", np.float32, 3)])
vertices["position"] = vertices_list

vbo = glGenBuffers(1)
glBindBuffer(GL_ARRAY_BUFFER, vbo)
glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

stride = vertices.strides[0]
loc_position = glGetAttribLocation(program, "position")
glEnableVertexAttribArray(loc_position)
glVertexAttribPointer(loc_position, 3, GL_FLOAT, False, stride, ctypes.c_void_p(0))


# ─── State ────────────────────────────────────────────────────────────────────

wireframe  = False
delta_time = 0.0
last_frame = 0.0

# Boat state
boat_x     = 0.0
boat_z     = 0.0
boat_angle = 0.0   # degrees, rotation around Y axis

BOAT_SPEED = 2.0   # units per second
BOAT_ROT   = 45.0  # degrees per second

# Shark state
shark_angle = 0.0  # degrees, advances every frame

# Sun spin state
sun_spin = 0.0  # degrees around Y, advances every frame
SUN_SPIN_SPEED = 5.0  # degrees per second

# Tracks which keys are currently held down
keys_pressed = set()


# ─── Camera ───────────────────────────────────────────────────────────────────

# Static camera (captured position)
STATIC_CAM_POS    = glm.vec3(-24.5841, 8.5859, 11.4405)
STATIC_CAM_TARGET = glm.vec3(-23.7209, 8.4037, 10.9698)
# STATIC_CAM_POS = glm.vec3(-10.7683, 20.6371, -34.0863)
# STATIC_CAM_TARGET = glm.vec3(-10.1016, 20.2820, -33.4311)
STATIC_CAM_UP     = glm.vec3(  0.0000,  1.0000,  0.0000)
STATIC_FOV        = 40.0

# Free camera state (only used when FREE_CAMERA = True)
cam_pos    = glm.vec3(STATIC_CAM_POS)
cam_front  = glm.normalize(STATIC_CAM_TARGET - STATIC_CAM_POS)
cam_up     = glm.vec3(STATIC_CAM_UP)
fov        = STATIC_FOV
yaw        = -135.0   # approximate yaw for the captured direction
pitch      = -35.0    # approximate pitch for the captured direction
last_x     = WIDTH  / 2.0
last_y     = HEIGHT / 2.0
first_mouse = True


# ─── Input ────────────────────────────────────────────────────────────────────

def key_event(window, key, scancode, action, mods):
    global wireframe, cam_pos, cam_front, cam_up, delta_time

    if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
        glfw.set_window_should_close(window, True)

    if key == glfw.KEY_P and action == glfw.PRESS:
        wireframe = not wireframe

    # Track held keys (used for boat movement and free-camera alike)
    if action == glfw.PRESS:
        keys_pressed.add(key)
    elif action == glfw.RELEASE:
        keys_pressed.discard(key)

    if not FREE_CAMERA:
        return

    # Free-camera controls (active only when FREE_CAMERA = True)
    if key == glfw.KEY_C and action == glfw.PRESS:
        target = cam_pos + cam_front
        print("\n── Camera snapshot ──────────────────────────")
        print(f"  cameraPos    = glm.vec3({cam_pos.x:.4f}, {cam_pos.y:.4f}, {cam_pos.z:.4f})")
        print(f"  cameraTarget = glm.vec3({target.x:.4f}, {target.y:.4f}, {target.z:.4f})")
        print(f"  cameraUp     = glm.vec3({cam_up.x:.4f}, {cam_up.y:.4f}, {cam_up.z:.4f})")
        print(f"  fov          = {fov:.1f}")
        print("─────────────────────────────────────────────\n")

    speed = 10.0 * delta_time
    if key == glfw.KEY_W and action in (glfw.PRESS, glfw.REPEAT):
        cam_pos += speed * cam_front
    if key == glfw.KEY_S and action in (glfw.PRESS, glfw.REPEAT):
        cam_pos -= speed * cam_front
    if key == glfw.KEY_A and action in (glfw.PRESS, glfw.REPEAT):
        cam_pos -= glm.normalize(glm.cross(cam_front, cam_up)) * speed
    if key == glfw.KEY_D and action in (glfw.PRESS, glfw.REPEAT):
        cam_pos += glm.normalize(glm.cross(cam_front, cam_up)) * speed


def mouse_callback(window, xpos, ypos):
    global yaw, pitch, last_x, last_y, first_mouse, cam_front

    if not FREE_CAMERA:
        return

    if first_mouse:
        last_x = xpos
        last_y = ypos
        first_mouse = False

    xoffset = (xpos - last_x) * 0.1
    yoffset = (last_y - ypos) * 0.1
    last_x = xpos
    last_y = ypos

    yaw   += xoffset
    pitch  = max(-89.0, min(89.0, pitch + yoffset))

    front = glm.vec3(
        math.cos(math.radians(yaw)) * math.cos(math.radians(pitch)),
        math.sin(math.radians(pitch)),
        math.sin(math.radians(yaw)) * math.cos(math.radians(pitch)),
    )
    cam_front = glm.normalize(front)


def scroll_callback(window, xoffset, yoffset):
    global fov
    if not FREE_CAMERA:
        return
    fov = max(10.0, min(90.0, fov - yoffset))


glfw.set_key_callback(window, key_event)
glfw.set_cursor_pos_callback(window, mouse_callback)
glfw.set_scroll_callback(window, scroll_callback)

if FREE_CAMERA:
    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)


# ─── Matrix helpers ───────────────────────────────────────────────────────────

def model_matrix(angle=0.0, rx=0.0, ry=1.0, rz=0.0,
                 tx=0.0, ty=0.0, tz=0.0,
                 sx=1.0, sy=1.0, sz=1.0):
    m = glm.mat4(1.0)
    m = glm.translate(m, glm.vec3(tx, ty, tz))
    if angle != 0.0:
        m = glm.rotate(m, math.radians(angle), glm.vec3(rx, ry, rz))
    m = glm.scale(m, glm.vec3(sx, sy, sz))
    return np.array(m)


# ─── Static view/projection (precomputed, used when FREE_CAMERA = False) ──────

mat_view_static = np.array(glm.lookAt(
    STATIC_CAM_POS, STATIC_CAM_TARGET, STATIC_CAM_UP
))
mat_proj_static = np.array(glm.perspective(
    glm.radians(STATIC_FOV), WIDTH / HEIGHT, 0.1, 200.0
))


# ─── Uniform locations (cached) ───────────────────────────────────────────────

loc_color      = glGetUniformLocation(program, "color")
loc_model      = glGetUniformLocation(program, "model")
loc_view       = glGetUniformLocation(program, "view")
loc_projection = glGetUniformLocation(program, "projection")


# ─── Boat input processing ────────────────────────────────────────────────────

def process_boat():
    """Called every frame. Reads keys_pressed and updates boat state."""
    global boat_x, boat_z, boat_angle

    if FREE_CAMERA:
        return  # WASD is used by free camera in that mode

    if glfw.KEY_A in keys_pressed:
        boat_angle += BOAT_ROT * delta_time   # CCW from above = left
    if glfw.KEY_D in keys_pressed:
        boat_angle -= BOAT_ROT * delta_time   # CW from above = right

    if glfw.KEY_W in keys_pressed or glfw.KEY_S in keys_pressed:
        # R_Y(boat_angle) * (0,0,1) = (sin θ, 0, cos θ)
        dx = math.sin(math.radians(boat_angle))
        dz = math.cos(math.radians(boat_angle))
        if glfw.KEY_W in keys_pressed:
            boat_x += dx * BOAT_SPEED * delta_time
            boat_z += dz * BOAT_SPEED * delta_time
        if glfw.KEY_S in keys_pressed:
            boat_x -= dx * BOAT_SPEED * delta_time
            boat_z -= dz * BOAT_SPEED * delta_time


# ─── Placement constants (tune these to reposition objects) ───────────────────
#
#   island1.obj   Y: -0.559 → 0.857  — lift by 0.559 so base sits at y=0,
#                                       top surface ends at y=1.416
#   lighthouse.obj Y: 0.000 → 9.802  — base at y=0, place on island top (1.416)
#   volcano_rock.obj Y: -1.363 → 5.598 — lift by 1.363 so base sits at y=0

ISLAND_SCALE     = 1.5    # island mesh is small in OBJ units — enlarge
LIGHTHOUSE_SCALE = 0.3   # lighthouse mesh is huge — shrink to match island
BOAT_SCALE = 0.6

ISLAND_POS = (
    -7.0,
    ISLAND_SCALE * 0.559,  # keeps island base on the sea plane (y=0)
    -6.0,
)
LIGHTHOUSE_POS = (
    -7.0,
    ISLAND_SCALE * 1.416,  # on scaled island top (was 1.416 unscaled)
    -6.0,
)
VOLCANO_POS   = ( 7.0,  1.363,  5.0)   # (x, ty, z)

# Shark swarm
SHARK_COUNT       = 3
SHARK_CENTER      = (0.0, 0, 0.0)   # orbit center (x, y, z)
SHARK_RADIUS      = 3.0               # orbit radius
SHARK_SPEED       = 25.0              # degrees per second
SHARK_FIN_SCALE   = 0.6               # uniform fin scale

# Sea ellipse: tweak SEA_SX / SEA_SZ to stretch the circle into an ellipse.
# With the current camera angle a wider X makes the horizon feel rounder.
SEA_SX = 40.0
SEA_SZ = 50.0
SUN_POS       = ( 20,  12.0,  -15)  # floats above the far edge of the scene
SUN_SCALE     = 2
# Rotate the sun upright so it faces the camera (built flat on XZ, camera looks +X)
# Start: 90° around Z lifts it to stand in the XY plane facing +X.
# Tweak SUN_ROT_ANGLE + SUN_ROT_AXIS until it looks right.
SUN_ROT_ANGLE   = 90.0              # degrees
SUN_ROT_AXIS    = (1.0, 0.0, 1.0)

CLOUD_ROT_ANGLE = 90.0              # degrees  (same starting point as sun)
CLOUD_ROT_AXIS  = (6, -2, 1.0)


# ─── Draw functions ───────────────────────────────────────────────────────────

def draw_boat():
    glUniform4f(loc_color, 0.55, 0.27, 0.07, 1.0)
    glUniformMatrix4fv(loc_model, 1, GL_TRUE,
        model_matrix(angle=boat_angle, ry=1.0, tx=boat_x, ty=0.4, tz=boat_z, sx=BOAT_SCALE, sy=BOAT_SCALE, sz=BOAT_SCALE))
    glDrawArrays(GL_TRIANGLES, start_boat, count_boat)


def draw_island():
    glUniform4f(loc_color, 0.76, 0.70, 0.50, 1.0)   # sandy yellow
    s = ISLAND_SCALE
    glUniformMatrix4fv(loc_model, 1, GL_TRUE,
        model_matrix(tx=ISLAND_POS[0], ty=ISLAND_POS[1], tz=ISLAND_POS[2],
                     sx=s, sy=s, sz=s))
    glDrawArrays(GL_TRIANGLES, start_island, count_island)


def draw_lighthouse():
    glUniform4f(loc_color, 0.95, 0.95, 0.92, 1.0)   # off-white
    s = LIGHTHOUSE_SCALE
    glUniformMatrix4fv(loc_model, 1, GL_TRUE,
        model_matrix(tx=LIGHTHOUSE_POS[0], ty=LIGHTHOUSE_POS[1], tz=LIGHTHOUSE_POS[2],
                     sx=s, sy=s, sz=s))
    glDrawArrays(GL_TRIANGLES, start_lh, count_lh)


def draw_volcano():
    glUniform4f(loc_color, 0.35, 0.30, 0.28, 1.0)   # dark basalt gray
    glUniformMatrix4fv(loc_model, 1, GL_TRUE,
        model_matrix(tx=VOLCANO_POS[0], ty=VOLCANO_POS[1], tz=VOLCANO_POS[2]))
    glDrawArrays(GL_TRIANGLES, start_volcano, count_volcano)


def draw_sun():
    glUniform4f(loc_color, 1.0, 0.85, 0.10, 1.0)   # warm yellow
    m = glm.mat4(1.0)
    m = glm.translate(m, glm.vec3(*SUN_POS))
    # Tilt to face camera first — establishes the sun's orientation in world space
    m = glm.rotate(m, math.radians(SUN_ROT_ANGLE), glm.vec3(*SUN_ROT_AXIS))
    # Spin around local Y (= face normal of the flat XZ sun before tilt)
    # Applied after tilt in the chain → acts in local space → spins in place as seen by camera
    m = glm.rotate(m, math.radians(sun_spin), glm.vec3(0.0, 1.0, 0.0))
    m = glm.scale(m, glm.vec3(SUN_SCALE, SUN_SCALE, SUN_SCALE))
    glUniformMatrix4fv(loc_model, 1, GL_TRUE, np.array(m))
    glDrawArrays(GL_TRIANGLES, start_sun, count_sun)


def draw_sharks():
    glUniform4f(loc_color, 0.25, 0.25, 0.30, 1.0)   # dark fin gray
    s = SHARK_FIN_SCALE
    for i in range(SHARK_COUNT):
        # Distribute fins evenly, all advancing at the same rate
        orbit_deg = shark_angle + i * (360.0 / SHARK_COUNT)
        orbit_rad = math.radians(orbit_deg)
        x = SHARK_CENTER[0] + SHARK_RADIUS * math.sin(orbit_rad)
        z = SHARK_CENTER[2] + SHARK_RADIUS * math.cos(orbit_rad)
        # Align fin forward (+X in model space) to the orbit tangent.
        # R_Y(α)*(1,0,0) = (cos α, 0, -sin α); tangent = (cos θ, 0, -sin θ) → α = orbit_deg
        face_angle = orbit_deg
        mat = model_matrix(
            angle=face_angle, ry=1.0,
            tx=x, ty=SHARK_CENTER[1], tz=z,
            sx=s, sy=s, sz=s,
        )
        glUniformMatrix4fv(loc_model, 1, GL_TRUE, mat)
        glDrawArrays(GL_TRIANGLES, start_fin, count_fin)


def draw_clouds():
    glUniform4f(loc_color, 1.0, 1.0, 1.0, 1.0)   # white
    for i, (start, count) in enumerate(clouds):
        _, tx, ty, tz, *_ = CLOUD_DEFS[i]
        m = glm.mat4(1.0)
        m = glm.translate(m, glm.vec3(tx, ty, tz))
        m = glm.rotate(m, math.radians(CLOUD_ROT_ANGLE), glm.vec3(*CLOUD_ROT_AXIS))
        glUniformMatrix4fv(loc_model, 1, GL_TRUE, np.array(m))
        glDrawArrays(GL_TRIANGLES, start, count)


def draw_sea():
    glUniform4f(loc_color, 0.05, 0.35, 0.65, 1.0)
    glUniformMatrix4fv(loc_model, 1, GL_TRUE,
        model_matrix(sx=SEA_SX, sy=1.0, sz=SEA_SZ))
    glDrawArrays(GL_TRIANGLES, start_sea, count_sea)


# ─── Render loop ──────────────────────────────────────────────────────────────

glfw.show_window(window)
glEnable(GL_DEPTH_TEST)

if FREE_CAMERA:
    print("\nFree camera ON  –  WASD move · Mouse look · Scroll zoom · C snapshot · P wireframe · ESC quit\n")
else:
    print("\nStatic camera  –  P wireframe · ESC quit  (set FREE_CAMERA=True to re-enable fly mode)\n")

while not glfw.window_should_close(window):
    now = glfw.get_time()
    delta_time = now - last_frame
    last_frame = now

    glfw.poll_events()
    process_boat()
    shark_angle += SHARK_SPEED * delta_time
    sun_spin    += SUN_SPIN_SPEED * delta_time

    glClearColor(0.53, 0.81, 0.98, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if wireframe else GL_FILL)

    if FREE_CAMERA:
        mat_view = np.array(glm.lookAt(cam_pos, cam_pos + cam_front, cam_up))
        mat_proj = np.array(glm.perspective(glm.radians(fov), WIDTH / HEIGHT, 0.1, 200.0))
    else:
        mat_view = mat_view_static
        mat_proj = mat_proj_static

    glUniformMatrix4fv(loc_view,       1, GL_TRUE, mat_view)
    glUniformMatrix4fv(loc_projection, 1, GL_TRUE, mat_proj)

    draw_sea()
    draw_clouds()
    draw_sharks()
    draw_sun()
    draw_island()
    draw_lighthouse()
    draw_volcano()
    draw_boat()

    glfw.swap_buffers(window)

glfw.terminate()
