import glm
import numpy as np

# ─── Window ───────────────────────────────────────────────────────────────────

WIDTH, HEIGHT = 800, 600

# ─── Frame timing ─────────────────────────────────────────────────────────────

delta_time = 0.0
last_frame = 0.0

# ─── Render state ─────────────────────────────────────────────────────────────

wireframe = False

# ─── Boat ─────────────────────────────────────────────────────────────────────

boat_x              = 0.0
boat_z              = 0.0
boat_angle          = 0.0    # degrees, Y-axis rotation
boat_moving_forward = False  # set by process_boat; read by bow spray emitters

BOAT_SPEED = 2.0   # world units per second
BOAT_ROT   = 45.0  # degrees per second

# ─── Sharks ───────────────────────────────────────────────────────────────────

shark_angle        = 0.0   # degrees, advances every frame
horizon_boat_angle = 0.0   # degrees, advances every frame

# ─── Sun ──────────────────────────────────────────────────────────────────────

sun_spin      = 0.0   # degrees, advances every frame
SUN_SPIN_SPEED = 5.0  # degrees per second

# ─── Coqueiro (escala em tempo real: A maior, Z menor) ───────────────────────

coqueiro_scale = 0.01
COQUEIRO_SCALE_MIN = 0.01
COQUEIRO_SCALE_MAX = 0.15
COQUEIRO_SCALE_SPEED = 0.18   # unidades de escala por segundo (mantém A/Z)

# ─── Input ────────────────────────────────────────────────────────────────────

keys_pressed = set()   # set of currently held glfw key codes


# ─── Camera ───────────────────────────────────────────────────────────────────

STATIC_CAM_POS    = glm.vec3(-24.5841,  8.5859, 11.4405)
STATIC_CAM_TARGET = glm.vec3(-23.7209,  8.4037, 10.9698)
STATIC_CAM_UP     = glm.vec3(  0.0000,  1.0000,  0.0000)
STATIC_FOV        = 40.0

mat_view_static = np.array(glm.lookAt(STATIC_CAM_POS, STATIC_CAM_TARGET, STATIC_CAM_UP))
mat_proj_static = np.array(glm.perspective(
    glm.radians(STATIC_FOV), WIDTH / HEIGHT, 0.1, 200.0
))
