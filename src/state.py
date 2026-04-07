import glm
import numpy as np

WIDTH, HEIGHT = 960, 720

delta_time = 0.0
last_frame = 0.0

wireframe = False

boat_x = 0.0
boat_z = 0.0
boat_angle = 0.0  # degrees, Y-axis rotation
boat_moving_forward = False  # True while W is held

BOAT_SPEED = 2.0  # world units per second
BOAT_ROT = 45.0  # degrees per second

shark_angle = 0.0  # degrees
horizon_boat_angle = 0.0  # degrees

sun_spin = 0.0  # degrees
SUN_SPIN_SPEED = 5.0  # degrees per second

coqueiro_scale = 0.01
COQUEIRO_SCALE_MIN = 0.01
COQUEIRO_SCALE_MAX = 0.15
COQUEIRO_SCALE_SPEED = 0.18  # scale units per second (Z increases, X decreases)

keys_pressed = set()  # currently held glfw key codes

STATIC_CAM_POS = glm.vec3(-24.5841, 8.5859, 11.4405)
STATIC_CAM_TARGET = glm.vec3(-23.7209, 8.4037, 10.9698)
STATIC_CAM_UP = glm.vec3(0.0000, 1.0000, 0.0000)
STATIC_FOV = 40.0

mat_view_static = np.array(glm.lookAt(STATIC_CAM_POS, STATIC_CAM_TARGET, STATIC_CAM_UP))
mat_proj_static = np.array(
    glm.perspective(glm.radians(STATIC_FOV), WIDTH / HEIGHT, 0.1, 200.0)
)
