import math
import numpy as np
import glm

# Single flat list — all objects share one VBO uploaded in projeto1.py
vertices_list = []


def model_matrix(angle=0.0, rx=0.0, ry=1.0, rz=0.0,
                 tx=0.0, ty=0.0, tz=0.0,
                 sx=1.0, sy=1.0, sz=1.0):
    m = glm.mat4(1.0)
    m = glm.translate(m, glm.vec3(tx, ty, tz))
    if angle != 0.0:
        m = glm.rotate(m, math.radians(angle), glm.vec3(rx, ry, rz))
    m = glm.scale(m, glm.vec3(sx, sy, sz))
    return np.array(m)


# ─── OBJ loader ───────────────────────────────────────────────────────────────

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
    modelo = load_model_from_file(filename)
    start = len(vertices_list)
    for face in modelo['faces']:
        for vid in circular_sliding_window_of_three(face[0]):
            vertices_list.append(modelo['vertices'][vid - 1])
    return start, len(vertices_list) - start


def load_obj_parts(filename):
    """Load OBJ with named objects. Returns {name: (start, count)} per part."""
    raw_verts = []
    current_name = '__default__'
    groups = []       # list of (name, [face_list])
    current_faces = []

    for line in open(filename, 'r'):
        if line.startswith('#'):
            continue
        values = line.split()
        if not values:
            continue
        if values[0] == 'v':
            raw_verts.append(values[1:4])
        elif values[0] in ('o', 'g'):
            if current_faces:
                groups.append((current_name, current_faces))
                current_faces = []
            current_name = values[1] if len(values) > 1 else '__default__'
        elif values[0] == 'f':
            face = [int(v.split('/')[0]) for v in values[1:]]
            current_faces.append(face)

    if current_faces:
        groups.append((current_name, current_faces))

    result = {}
    for name, faces in groups:
        start = len(vertices_list)
        for face in faces:
            for vid in circular_sliding_window_of_three(face):
                vertices_list.append(raw_verts[vid - 1])
        count = len(vertices_list) - start
        if count > 0:
            result[name] = (start, count)

    return result


# ─── Procedural geometry builders ─────────────────────────────────────────────

def make_sun(R_inner=1.0, R_outer=1.7, N=12):
    """
    2D sun: N-gon body (triangle fan) + one outward spike per edge.
    Built flat on the XZ plane, centered at origin.
    """
    start = len(vertices_list)
    step = 2 * math.pi / N
    rim  = [(math.cos(i * step), math.sin(i * step)) for i in range(N)]

    for i in range(N):
        cx, cz = rim[i]
        nx, nz = rim[(i + 1) % N]
        vertices_list.append([0.0,          0.0, 0.0         ])
        vertices_list.append([R_inner * cx, 0.0, R_inner * cz])
        vertices_list.append([R_inner * nx, 0.0, R_inner * nz])

    for i in range(N):
        cx, cz = rim[i]
        nx, nz = rim[(i + 1) % N]
        mid_a  = (i + 0.5) * step
        vertices_list.append([R_inner * cx,            0.0, R_inner * cz           ])
        vertices_list.append([R_inner * nx,            0.0, R_inner * nz           ])
        vertices_list.append([R_outer * math.cos(mid_a), 0.0, R_outer * math.sin(mid_a)])

    return start, len(vertices_list) - start


def make_shark_fin():
    """
    Single shark fin in the XY plane, base centered at local origin.
    Two triangles: main body + back-swept notch.
    """
    start   = len(vertices_list)
    p_front = [-0.20, 0.00, 0.0]
    p_back  = [ 0.30, 0.00, 0.0]
    p_tip   = [ 0.05, 0.80, 0.0]
    p_notch = [ 0.30, 0.28, 0.0]

    vertices_list.append(p_front)
    vertices_list.append(p_back)
    vertices_list.append(p_tip)
    vertices_list.append(p_back)
    vertices_list.append(p_notch)
    vertices_list.append(p_tip)

    return start, len(vertices_list) - start


def make_cloud(seed, a=2.5, b=1.4, n_circles=12, r_min=0.3, r_max=0.8, N=16, y=0.05):
    """
    Cloud: overlapping circles distributed inside an ellipse (a × b).
    Centers sampled with a fixed seed → reproducible shape.
    Circle radius lerps from r_max at center to r_min at the boundary.
    Geometry is in local space; position via model matrix.
    """
    rng   = np.random.default_rng(seed)
    start = len(vertices_list)
    step  = 2 * math.pi / N

    centers  = []
    attempts = 0
    while len(centers) < n_circles and attempts < n_circles * 20:
        x = rng.uniform(-a, a)
        z = rng.uniform(-b, b)
        if (x / a) ** 2 + (z / b) ** 2 <= 1.0:
            centers.append((x, z))
        attempts += 1

    for (cx, cz) in centers:
        dist = math.sqrt((cx / a) ** 2 + (cz / b) ** 2)
        r    = r_max + (r_min - r_max) * dist
        for i in range(N):
            a1 = i * step
            a2 = (i + 1) * step
            vertices_list.append([cx,                     y, cz                    ])
            vertices_list.append([cx + r * math.cos(a1),  y, cz + r * math.sin(a1)])
            vertices_list.append([cx + r * math.cos(a2),  y, cz + r * math.sin(a2)])

    return start, len(vertices_list) - start


def make_sphere(radius=1.0, stacks=8, slices=8):
    """UV sphere centered at origin."""
    start = len(vertices_list)
    for i in range(stacks):
        phi0 = math.pi * i       / stacks - math.pi / 2
        phi1 = math.pi * (i + 1) / stacks - math.pi / 2
        for j in range(slices):
            th0 = 2 * math.pi * j       / slices
            th1 = 2 * math.pi * (j + 1) / slices
            p = [
                [radius * math.cos(phi0) * math.cos(th0), radius * math.sin(phi0), radius * math.cos(phi0) * math.sin(th0)],
                [radius * math.cos(phi0) * math.cos(th1), radius * math.sin(phi0), radius * math.cos(phi0) * math.sin(th1)],
                [radius * math.cos(phi1) * math.cos(th0), radius * math.sin(phi1), radius * math.cos(phi1) * math.sin(th0)],
                [radius * math.cos(phi1) * math.cos(th1), radius * math.sin(phi1), radius * math.cos(phi1) * math.sin(th1)],
            ]
            vertices_list.append(p[0]); vertices_list.append(p[1]); vertices_list.append(p[2])
            vertices_list.append(p[1]); vertices_list.append(p[3]); vertices_list.append(p[2])
    return start, len(vertices_list) - start


def make_sea_circle(radius=1.0, N=64):
    """
    Filled circle on the XZ plane (triangle fan).
    Scale sx/sz in the model matrix to stretch into an ellipse.
    """
    start = len(vertices_list)
    step  = 2 * math.pi / N
    for i in range(N):
        a1 = i * step
        a2 = (i + 1) * step
        vertices_list.append([0.0,                   0.0, 0.0                  ])
        vertices_list.append([radius * math.cos(a1), 0.0, radius * math.sin(a1)])
        vertices_list.append([radius * math.cos(a2), 0.0, radius * math.sin(a2)])
    return start, len(vertices_list) - start


# ─── Load all geometry (runs at import time) ──────────────────────────────────

boat_parts = load_obj_parts('models/barco_partes_separadas.obj')
start_island,  count_island  = load_obj('models/island1.obj')
lh_parts = load_obj_parts('models/lighthouse_partes_separadas.obj')
coqueiro_parts = load_obj_parts('models/coqueiro_separado.obj')
start_volcano, count_volcano = load_obj('models/volcano_rock.obj')
start_sun,     count_sun     = make_sun(R_inner=.8, R_outer=1.5, N=12)
start_fin,     count_fin     = make_shark_fin()
start_sea,     count_sea     = make_sea_circle(radius=1.0, N=64)
start_particle, count_particle = make_sphere(radius=1.0, stacks=8, slices=8)

# Each entry: (seed, world_x, world_y, world_z, ellipse_a, ellipse_b, n_circles)
CLOUD_DEFS = [
    (11, 10.0, 12, -20.0, 3, 1.5, 100),
]

clouds = []
for (seed, *_rest) in CLOUD_DEFS:
    a, b, n = _rest[3], _rest[4], _rest[5]
    s, c = make_cloud(seed=seed, a=a, b=b, n_circles=n)
    clouds.append((s, c))
