import glm
import numpy as np

# ─── Window ───────────────────────────────────────────────────────────────────

WIDTH, HEIGHT = 800, 600

# ─── Dev toggles ──────────────────────────────────────────────────────────────

FREE_CAMERA = False   # set True to re-enable WASD + mouse fly camera

# ─── Frame timing ─────────────────────────────────────────────────────────────

delta_time = 0.0
last_frame = 0.0

# ─── Render state ─────────────────────────────────────────────────────────────

wireframe = False

# ─── Boat ─────────────────────────────────────────────────────────────────────

boat_x     = 0.0
boat_z     = 0.0
boat_angle = 0.0   # degrees, Y-axis rotation

BOAT_SPEED = 2.0   # world units per second
BOAT_ROT   = 45.0  # degrees per second

# ─── Sharks ───────────────────────────────────────────────────────────────────

shark_angle = 0.0  # degrees, advances every frame

# ─── Sun ──────────────────────────────────────────────────────────────────────

sun_spin      = 0.0   # degrees, advances every frame
SUN_SPIN_SPEED = 5.0  # degrees per second

# ─── Coqueiro (escala em tempo real: A maior, Z menor) ───────────────────────

coqueiro_scale = 0.07
COQUEIRO_SCALE_MIN = 0.03
COQUEIRO_SCALE_MAX = 0.50
COQUEIRO_SCALE_SPEED = 0.18   # unidades de escala por segundo (mantém A/Z)

# ─── Input ────────────────────────────────────────────────────────────────────

keys_pressed = set()   # set of currently held glfw key codes

# ─── Camera ───────────────────────────────────────────────────────────────────

STATIC_CAM_POS    = glm.vec3(-24.5841,  8.5859, 11.4405)
STATIC_CAM_TARGET = glm.vec3(-23.7209,  8.4037, 10.9698)
STATIC_CAM_UP     = glm.vec3(  0.0000,  1.0000,  0.0000)
STATIC_FOV        = 40.0

# Free-camera mutable state (only active when FREE_CAMERA = True)
cam_pos    = glm.vec3(STATIC_CAM_POS)
cam_front  = glm.normalize(STATIC_CAM_TARGET - STATIC_CAM_POS)
cam_up     = glm.vec3(STATIC_CAM_UP)
fov        = STATIC_FOV
yaw        = -135.0
pitch      = -35.0
last_x     = WIDTH  / 2.0
last_y     = HEIGHT / 2.0
first_mouse = True

# Precomputed static view / projection (reused every frame when FREE_CAMERA=False)
mat_view_static = np.array(glm.lookAt(STATIC_CAM_POS, STATIC_CAM_TARGET, STATIC_CAM_UP))
mat_proj_static = np.array(glm.perspective(
    glm.radians(STATIC_FOV), WIDTH / HEIGHT, 0.1, 200.0
))
