import math
import numpy as np
import glm

vertices_list = []


def model_matrix(
    angle=0.0, rx=0.0, ry=1.0, rz=0.0, tx=0.0, ty=0.0, tz=0.0, sx=1.0, sy=1.0, sz=1.0
):
    """Build a TRS model matrix (translate -> rotate -> scale).

    Args:
        angle: rotation amount in degrees.
        rx, ry, rz: rotation axis vector components.
        tx, ty, tz: translation in world units.
        sx, sy, sz: scale factors per axis.

    Returns:
        4x4 numpy array in row-major order, ready for glUniformMatrix4fv with GL_TRUE.
    """
    m = glm.mat4(1.0)
    m = glm.translate(m, glm.vec3(tx, ty, tz))
    if angle != 0.0:
        m = glm.rotate(m, math.radians(angle), glm.vec3(rx, ry, rz))
    m = glm.scale(m, glm.vec3(sx, sy, sz))
    return np.array(m)


# OBJ loader


def load_model_from_file(filename):
    """Parse a .obj file and return raw geometry data.

    Args:
        filename: path to the .obj file.

    Returns:
        Dict with keys:
            'vertices': list of [x, y, z] strings,
            'texture':  list of [u, v] strings,
            'faces':    list of (vertex_indices, tex_indices, None) tuples.
    """
    vertices = []
    texture_coords = []
    faces = []
    for line in open(filename, "r"):
        if line.startswith("#"):
            continue
        values = line.split()
        if not values:
            continue
        if values[0] == "v":
            vertices.append(values[1:4])
        elif values[0] == "vt":
            texture_coords.append(values[1:3])
        elif values[0] == "f":
            face = []
            face_texture = []
            for v in values[1:]:
                w = v.split("/")
                face.append(int(w[0]))
                face_texture.append(int(w[1]) if len(w) >= 2 and w[1] else 0)
            faces.append((face, face_texture, None))
    return {"vertices": vertices, "texture": texture_coords, "faces": faces}


def circular_sliding_window_of_three(arr):
    """Triangulate a polygon face by fanning index triplets around its perimeter.

    A triangle face is returned as-is. For faces with more vertices, produces
    a strip of overlapping triplets by wrapping the first index at the end,
    effectively converting an n-gon into (n-1) triangles.

    Args:
        arr: list of vertex indices forming a single polygon face.

    Returns:
        Flat list of vertex indices grouped in consecutive triangles.
    """
    if len(arr) == 3:
        return arr
    circular_arr = arr + [arr[0]]
    result = []
    for i in range(len(circular_arr) - 2):
        result.extend(circular_arr[i : i + 3])
    return result


def load_obj(filename):
    """Load a .obj file and append its triangulated vertices to vertices_list.

    Args:
        filename: path to the .obj file.

    Returns:
        (start, count) tuple - byte offset and vertex count within vertices_list.
    """
    modelo = load_model_from_file(filename)
    start = len(vertices_list)
    for face in modelo["faces"]:
        for vid in circular_sliding_window_of_three(face[0]):
            vertices_list.append(modelo["vertices"][vid - 1])
    return start, len(vertices_list) - start


def load_obj_parts(filename):
    """Load a .obj file that contains named objects, keeping each part separate.

    Splits geometry by 'o' or 'g' directives so each named mesh can be
    drawn and colored independently. Only vertex positions are loaded;
    texture coordinates and normals are ignored.

    Args:
        filename: path to the .obj file with named object groups.

    Returns:
        Dict mapping each part name to a (start, count) tuple within vertices_list.
    """
    raw_verts = []
    current_name = "__default__"
    groups = []  # list of (name, [face_list])
    current_faces = []

    for line in open(filename, "r"):
        if line.startswith("#"):
            continue
        values = line.split()
        if not values:
            continue
        if values[0] == "v":
            raw_verts.append(values[1:4])
        elif values[0] in ("o", "g"):
            if current_faces:
                groups.append((current_name, current_faces))
                current_faces = []
            current_name = values[1] if len(values) > 1 else "__default__"
        elif values[0] == "f":
            face = [int(v.split("/")[0]) for v in values[1:]]
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


# Procedural geometry builders


def make_sun(R_inner=1.0, R_outer=1.7, N=12):
    """Build a 2D sun shape: a filled N-gon body with one outward spike per edge.

    Geometry is flat on the XZ plane centered at the origin. Two passes over
    the N rim points: the first fills the polygon body as a triangle fan from
    the center; the second adds one isoceles spike per edge, with its tip at
    the midpoint angle between adjacent rim vertices projected to R_outer.

    Args:
        R_inner: radius of the central polygon body.
        R_outer: radius at the tip of each spike.
        N:       number of polygon sides (and spikes).

    Returns:
        (start, count) tuple within vertices_list.
    """
    start = len(vertices_list)
    step = 2 * math.pi / N
    rim = [(math.cos(i * step), math.sin(i * step)) for i in range(N)]

    for i in range(N):
        cx, cz = rim[i]
        nx, nz = rim[(i + 1) % N]
        vertices_list.append([0.0, 0.0, 0.0])
        vertices_list.append([R_inner * cx, 0.0, R_inner * cz])
        vertices_list.append([R_inner * nx, 0.0, R_inner * nz])

    for i in range(N):
        cx, cz = rim[i]
        nx, nz = rim[(i + 1) % N]
        mid_a = (i + 0.5) * step
        vertices_list.append([R_inner * cx, 0.0, R_inner * cz])
        vertices_list.append([R_inner * nx, 0.0, R_inner * nz])
        vertices_list.append(
            [R_outer * math.cos(mid_a), 0.0, R_outer * math.sin(mid_a)]
        )

    return start, len(vertices_list) - start


def make_shark_fin():
    """Build a single shark fin shape on the XZ plane, base centered at the origin.

    Defined by four hand-placed points forming two triangles: one for the main
    body and one for the back-swept notch that gives the fin its silhouette.

    Returns:
        (start, count) tuple within vertices_list.
    """
    start = len(vertices_list)
    p_front = [-0.20, 0.00, 0.0]
    p_back = [0.30, 0.00, 0.0]
    p_tip = [0.05, 0.80, 0.0]
    p_notch = [0.30, 0.28, 0.0]

    vertices_list.append(p_front)
    vertices_list.append(p_back)
    vertices_list.append(p_tip)
    vertices_list.append(p_back)
    vertices_list.append(p_notch)
    vertices_list.append(p_tip)

    return start, len(vertices_list) - start


def make_sphere(radius=1.0, stacks=8, slices=8):
    """Build a UV sphere centered at the origin.

    Iterates over a latitude/longitude grid. Each (stack, slice) cell produces
    two triangles from its four corner vertices, computed from spherical
    coordinates (phi for latitude, theta for longitude).

    Args:
        radius: sphere radius in local units.
        stacks: number of latitudinal subdivisions (rings from pole to pole).
        slices: number of longitudinal subdivisions (segments around the equator).

    Returns:
        (start, count) tuple within vertices_list.
    """
    start = len(vertices_list)
    for i in range(stacks):
        phi0 = math.pi * i / stacks - math.pi / 2
        phi1 = math.pi * (i + 1) / stacks - math.pi / 2
        for j in range(slices):
            th0 = 2 * math.pi * j / slices
            th1 = 2 * math.pi * (j + 1) / slices
            p = [
                [
                    radius * math.cos(phi0) * math.cos(th0),
                    radius * math.sin(phi0),
                    radius * math.cos(phi0) * math.sin(th0),
                ],
                [
                    radius * math.cos(phi0) * math.cos(th1),
                    radius * math.sin(phi0),
                    radius * math.cos(phi0) * math.sin(th1),
                ],
                [
                    radius * math.cos(phi1) * math.cos(th0),
                    radius * math.sin(phi1),
                    radius * math.cos(phi1) * math.sin(th0),
                ],
                [
                    radius * math.cos(phi1) * math.cos(th1),
                    radius * math.sin(phi1),
                    radius * math.cos(phi1) * math.sin(th1),
                ],
            ]
            vertices_list.append(p[0])
            vertices_list.append(p[1])
            vertices_list.append(p[2])
            vertices_list.append(p[1])
            vertices_list.append(p[3])
            vertices_list.append(p[2])
    return start, len(vertices_list) - start


def make_sea_circle(radius=1.0, N=64):
    """Build a filled circle on the XZ plane as a triangle fan.

    Scale sx and sz in the model matrix to stretch the circle into an ellipse.

    Args:
        radius: circle radius before any model matrix scaling.
        N:      number of triangle fan segments (higher = smoother edge).

    Returns:
        (start, count) tuple within vertices_list.
    """
    start = len(vertices_list)
    step = 2 * math.pi / N
    for i in range(N):
        a1 = i * step
        a2 = (i + 1) * step
        vertices_list.append([0.0, 0.0, 0.0])
        vertices_list.append([radius * math.cos(a1), 0.0, radius * math.sin(a1)])
        vertices_list.append([radius * math.cos(a2), 0.0, radius * math.sin(a2)])
    return start, len(vertices_list) - start


# Load all geometry (runs at import time)

boat_parts = load_obj_parts("models/barco_partes_separadas.obj")
start_island, count_island = load_obj("models/island1.obj")
lh_parts = load_obj_parts("models/lighthouse_partes_separadas.obj")
coqueiro_parts = load_obj_parts("models/coqueiro_separado.obj")
start_volcano, count_volcano = load_obj("models/volcano_rock.obj")
start_sun, count_sun = make_sun(R_inner=0.8, R_outer=1.5, N=12)
start_fin, count_fin = make_shark_fin()
start_sea, count_sea = make_sea_circle(radius=1.0, N=64)
start_particle, count_particle = make_sphere(radius=1.0, stacks=8, slices=8)
