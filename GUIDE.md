# Ocean Scene – Didactic Guide

> A deep-dive into the design decisions behind every non-obvious piece of this
> OpenGL project.  Assumes you already know what a vertex, a shader, and a
> matrix are, but not necessarily *why* things are built the way they are.

---

## Table of Contents

1. [Project File Map](#1-project-file-map)
2. [The Single GPU Buffer – Why All Geometry Lives Together](#2-the-single-gpu-buffer)
3. [delta\_time – Frame-rate Independent Animation](#3-delta_time)
4. [The model\_matrix Helper and TRS Order](#4-the-model_matrix-helper-and-trs-order)
5. [Local vs World Coordinates](#5-local-vs-world-coordinates)
6. [Multi-Part Objects: Slicing Without Losing Cohesion](#6-multi-part-objects)
7. [The `_local_to_world` Static Method](#7-the-_local_to_world-static-method)
8. [The `make_sun` Algorithm](#8-the-make_sun-algorithm)
9. [The `make_sphere` (UV Sphere) Algorithm](#9-the-make_sphere-uv-sphere-algorithm)
10. [Boat Bobbing – Why Two Sine Waves?](#10-boat-bobbing)
11. [Bow Spray Particles – Vectors, Not Sin Waves](#11-bow-spray-particles)
12. [The Particle System](#12-the-particle-system)
13. [Circular Orbits – Sharks, Horizon Boats, Sun Spin](#13-circular-orbits)
14. [The Rendering Pipeline End-to-End](#14-the-rendering-pipeline-end-to-end)

---

## 1. Project File Map

```
main_scene.py        ← entry point: window, GPU upload, render loop
src/
  state.py           ← global mutable game state (positions, angles, flags)
  geometry.py        ← ALL geometry: OBJ loaders + procedural builders + model_matrix
  scene.py           ← Scene class: one draw_* method per object
  particles.py       ← ParticleEmitter: physics + lifetime + draw
  input.py           ← GLFW key callbacks and per-frame key processing
  shader_s.py        ← thin Shader wrapper (compile, link, use)
shaders/
  vertex_shader.vs   ← transforms position through model/view/projection
  fragment_shader.fs ← outputs a single flat uniform color
models/
  barco_partes_separadas.obj        ← boat, split into named objects
  lighthouse_partes_separadas.obj   ← lighthouse, split into named objects
  coqueiro_separado.obj             ← coconut tree, split into named objects
  island1.obj, volcano_rock.obj     ← single-part OBJ models
```

**The key insight about this layout**: `state.py` has zero OpenGL calls –
it is plain Python data. `geometry.py` has zero animation logic – it just
builds meshes.  `scene.py` bridges them: it reads state to decide *where*
and *how* to draw, then issues OpenGL calls.  This separation makes each file
easy to reason about in isolation.

---

## 2. The Single GPU Buffer

### Why one big VBO?

At startup, `main_scene.py` does this sequence:

```python
# geometry.py populates vertices_list at import time
vertices = np.zeros(len(geometry.vertices_list), [("position", np.float32, 3)])
vertices["position"] = geometry.vertices_list

vbo = glGenBuffers(1)
glBindBuffer(GL_ARRAY_BUFFER, vbo)
glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
```

Every piece of geometry – the sea, the boat, the sun, the sphere used for
particles, all OBJ models – is packed into **one contiguous numpy array**
that is uploaded to the GPU a single time, before the render loop starts.

Each geometry builder returns a `(start, count)` pair that records its
slice within this array:

```python
start_sun, count_sun   = make_sun(...)
start_sea, count_sea   = make_sea_circle(...)
start_particle, count_particle = make_sphere(...)
boat_parts = load_obj_parts(...)  # dict of name -> (start, count)
```

Drawing an object then becomes a cheap pointer into that already-uploaded
buffer:

```python
glDrawArrays(GL_TRIANGLES, geometry.start_sun, geometry.count_sun)
```

**Why `GL_STATIC_DRAW`?**  
The raw vertex positions never change at runtime – animation is handled
entirely through the `model` uniform matrix.  `GL_STATIC_DRAW` tells the
driver the buffer will be written once and read many times, allowing it to
place the data in faster GPU-side memory.

**Why not one VBO per object?**  
Switching a bound VBO has a small cost.  More importantly, keeping everything
in one buffer simplifies the upload code: one `glBufferData`, one
`glVertexAttribPointer`, done.  Slicing by `(start, count)` is free.

---

## 3. `delta_time`

### The problem it solves

Imagine this animation in a naive loop:

```python
boat_angle += 1.0  # degrees per frame
```

On a machine running at 60 FPS the boat rotates 60 °/s.
On a machine running at 120 FPS it rotates 120 °/s.
Same code, wildly different behavior.

### The solution

```python
# main_scene.py – inside the render loop
now = glfw.get_time()
state.delta_time = now - state.last_frame
state.last_frame = now
```

`glfw.get_time()` returns wall-clock seconds since GLFW was initialized.
`delta_time` is therefore the number of seconds that elapsed since the last
frame – typically something like `0.0166` at 60 FPS or `0.0083` at 120 FPS.

Every quantity that should change at a **per-second** rate is multiplied by
`delta_time` before being applied:

```python
# input.py
state.boat_angle += state.BOAT_ROT * state.delta_time   # 45°/s regardless of FPS

# main_scene.py
state.shark_angle += scene.SHARK_SPEED * state.delta_time   # 25°/s
state.sun_spin    += state.SUN_SPIN_SPEED * state.delta_time # 5°/s
```

The unit of `BOAT_ROT`, `SHARK_SPEED`, etc. is "per second", not "per frame".
This is the standard game-loop pattern and it makes the scene behave
identically on any hardware.

---

## 4. The `model_matrix` Helper and TRS Order

### What it does

```python
def model_matrix(angle=0, rx=0, ry=1, rz=0, tx=0, ty=0, tz=0, sx=1, sy=1, sz=1):
    m = glm.mat4(1.0)           # identity
    m = glm.translate(m, glm.vec3(tx, ty, tz))
    if angle != 0.0:
        m = glm.rotate(m, math.radians(angle), glm.vec3(rx, ry, rz))
    m = glm.scale(m, glm.vec3(sx, sy, sz))
    return np.array(m)
```

It builds a **TRS matrix**: Translate × Rotate × Scale.

### Why this exact order?

Matrix multiplication is applied **right-to-left** to a vertex:

```
final_pos = T × R × S × local_vertex
```

Which means, reading left-to-right in the order operations happen:

1. **Scale** the vertex around the local origin.
2. **Rotate** the already-scaled vertex around the local origin.
3. **Translate** to the final world position.

This is the "natural" order: you sculpt an object in its own space, orient
it, then place it in the world.

**If you reversed S and T** you would scale from the *world* origin, which
would also move the object (scaling a translated object from the origin changes
its position).  Try it mentally: scale a cube that is sitting 5 units away
from the origin by 2× – it will jump to 10 units away.  With TRS order the
scale only inflates the cube in place.

**If you put T before R** the object would orbit the world origin when you
rotate, instead of spinning in place.

### Row-major vs column-major and `GL_TRUE`

`glm` stores matrices in column-major order (OpenGL convention).  NumPy
`np.array(m)` preserves that column-major layout.  Passing `GL_TRUE` to
`glUniformMatrix4fv` tells OpenGL to **transpose** the matrix on upload,
converting it back to the row-major form the GLSL shader expects internally.
Without `GL_TRUE` the matrix would be transposed by accident, producing
wrong results.

---

## 5. Local vs World Coordinates

Every OBJ model is authored around its own **local origin** (often the
centroid of the model or its base).  A vertex position inside an OBJ file
is a **local coordinate**.

The **model matrix** is what converts local coordinates to **world
coordinates**:

```
world_position = model_matrix × local_position
```

The **view matrix** converts world coordinates to **camera space**, and the
**projection matrix** converts camera space to **clip space** (what appears
on screen):

```
clip_position = projection × view × model × local_position
```

This chain lives in the vertex shader:

```glsl
gl_Position = projection * view * model * vec4(position, 1.0);
```

### Practical consequence

When you place the lighthouse at `(-7.0, 2.12, -6.0)`, you do not move any
vertex in the buffer.  You upload a new `model` uniform that encodes that
translation, and the GPU computes `(-7.0 + lx, 2.12 + ly, -6.0 + lz)` for
every vertex at draw time.  The buffer itself never changes.

---

## 6. Multi-Part Objects

### The problem

A boat has five visually distinct parts: hull bottom, hull top, cabin, cabin
roof, chimney.  They need different colors, but they move as one rigid body.

### The solution: `load_obj_parts`

The OBJ format allows **named objects** inside a single file:

```
o boat_bottom
f 1/1 2/2 3/3 ...
o boat_top
f 10/1 11/2 12/3 ...
```

`load_obj_parts` reads these `o`/`g` directives and records which vertices
belong to which name:

```python
result[name] = (start, count)   # slice in the global vertices_list
```

All parts are still appended to the **same** global buffer, just consecutively.

### How they move together

The trick is to compute **one** model matrix per frame for the whole boat,
then draw every part through that same matrix, only changing the color uniform
between parts:

```python
mat = model_matrix(angle=state.boat_angle, ry=1.0,
                   tx=state.boat_x, ty=..., tz=state.boat_z,
                   sx=s, sy=s, sz=s)
glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)   # set ONCE

for name, (start, count) in geometry.boat_parts.items():
    color = self.BOAT_PART_COLORS.get(name, (1,1,1,1))
    glUniform4f(self.loc_color, *color)               # change color per part
    glDrawArrays(GL_TRIANGLES, start, count)          # draw the slice
```

Because the model matrix is not changed between `glDrawArrays` calls, every
part is transformed identically – they move as a single rigid object.
The color uniform changes per-part because it is cheap (4 floats vs a 4×4
matrix).

This pattern is used for the boat, the lighthouse, and the coconut trees.

---

## 7. The `_local_to_world` Static Method

```python
@staticmethod
def _local_to_world(local, scale, angle_deg, tx, ty, tz):
    lx, ly, lz = local
    sx, sy, sz = lx * scale, ly * scale, lz * scale
    a = math.radians(angle_deg)
    return (
        sx * math.cos(a) + sz * math.sin(a) + tx,
        sy + ty,
        -sx * math.sin(a) + sz * math.cos(a) + tz,
    )
```

### Why does this exist?

The GPU knows where the chimney top is after applying the model matrix.
But the **CPU** does not – the GPU result is never read back.  When we need
to position a particle emitter at the chimney top in world space, we have to
re-do the same arithmetic on the CPU side.

### Why `@staticmethod`?

This is a **pure function**: it takes inputs and returns a result with no
side effects and no access to `self` or `cls`.  Making it a `@staticmethod`
signals exactly that: "this helper belongs logically inside `Scene` but does
not depend on any instance state".  It could be a module-level function; the
static method placement is organizational.

### What the math does

The model matrix for the boat applies, in order: scale → Y-rotation →
translation.  This method manually reproduces that sequence:

1. **Scale**: `sx = lx * scale`
2. **Y-axis rotation by `angle_deg`** – a rotation around Y transforms `(x, z)`
   by the standard 2D rotation formula:

   ```
   x' =  x·cos(a) + z·sin(a)
   z' = -x·sin(a) + z·cos(a)
   y' = y   (unchanged by Y-rotation)
   ```

3. **Translate**: add `(tx, ty, tz)`.

This is exactly what `model_matrix` computes for a vertex, but done explicitly
in Python so the result is a `(wx, wy, wz)` tuple the CPU can use.

---

## 8. The `make_sun` Algorithm

```python
def make_sun(R_inner=1.0, R_outer=1.7, N=12):
```

The sun is a 2D shape lying flat on the XZ plane.  It has two components:

### Component 1 – The central polygon (N-gon body)

Evenly distribute `N` points around a circle of radius `R_inner`:

```python
step = 2 * math.pi / N
rim = [(math.cos(i * step), math.sin(i * step)) for i in range(N)]
```

Then for each consecutive pair of rim points, emit a triangle whose third
vertex is the center (0, 0, 0):

```
center → rim[i] → rim[i+1]
```

This is a **triangle fan** stored as individual triangles.  With `N=12` this
produces a 12-sided polygon that looks like a circle at scene scale.

```
     *
   * | *
  *  |  *
  *--C--*    C = center
  *  |  *
   * | *
     *
```

### Component 2 – The spikes

Each edge of the polygon (from `rim[i]` to `rim[i+1]`) gets one outward spike.
The spike tip is the midpoint angle between `rim[i]` and `rim[i+1]`, projected
to `R_outer`:

```python
mid_a = (i + 0.5) * step
tip = [R_outer * math.cos(mid_a), 0.0, R_outer * math.sin(mid_a)]
```

The spike is one triangle: `rim[i] → rim[i+1] → tip`.

```
          tip (R_outer)
         / \
rim[i]--/---\--rim[i+1]  (R_inner)
```

With `N=12` this produces 12 spikes evenly spaced around the polygon – the
classic cartoon-sun silhouette.

### Why XZ plane?

The sun model is created flat on XZ (Y = 0).  In `draw_sun` it is then
rotated 90° around the axis `(1, 0, 1)` to stand upright and face the camera,
then additionally spun around Y by `state.sun_spin` each frame:

```python
m = glm.rotate(m, math.radians(self.SUN_ROT_ANGLE), glm.vec3(*self.SUN_ROT_AXIS))
m = glm.rotate(m, math.radians(state.sun_spin), glm.vec3(0, 1, 0))
```

Building 2D shapes on XZ is convenient because Y is "up" in this scene's
convention, so a flat shape on XZ is a "floor" that can be tilted by the
model matrix into any orientation.

---

## 9. The `make_sphere` (UV Sphere) Algorithm

```python
def make_sphere(radius=1.0, stacks=8, slices=8):
```

A UV sphere parameterizes the surface with:
- **phi** (latitude): from −π/2 (south pole) to +π/2 (north pole)
- **theta** (longitude): from 0 to 2π around the equator

For each cell in the `stacks × slices` grid, four corner vertices are
computed using the spherical-to-Cartesian conversion:

```
x = radius · cos(phi) · cos(theta)
y = radius · sin(phi)
z = radius · cos(phi) · sin(theta)
```

Each cell becomes two triangles (a quad split along the diagonal):

```
p[0]---p[1]
 |   / |
 |  /  |
p[2]---p[3]

Triangle 1: p[0], p[1], p[2]
Triangle 2: p[1], p[3], p[2]
```

**Why `y = radius · sin(phi)`?**  
At the equator `phi = 0`, so `sin(0) = 0` and `y = 0` – the equator is
at mid-height.  At the north pole `phi = π/2`, `sin(π/2) = 1`, so `y = radius`.
At the south pole `phi = −π/2`, `y = −radius`.  This is the standard
parametric sphere formula.

**Why `cos(phi)` in x and z?**  
`cos(phi)` is the "radius of the latitude ring" at angle phi.  At the equator
`cos(0) = 1`, so x/z span the full `radius`.  At the poles `cos(±π/2) = 0`,
so x/z collapse to zero – that is the pole point.

This sphere is used exclusively for **particles**: each particle is a scaled
sphere, making particles look like small blobs.

---

## 10. Boat Bobbing

### Why two sine waves?

```python
t = self.BOAT_BOB_SPEED * state.last_frame
bob = self.BOAT_BOB_AMPLITUDE * (
    0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
)
```

A single sine wave produces perfectly mechanical, metronome-like motion.
Real water causes boats to bob at multiple overlapping frequencies
simultaneously (wind waves + swell + chop).

Summing two sine waves at **incommensurable frequencies** (1.0 and 2.3 are not
integer multiples) produces a signal that never exactly repeats, making the
motion feel organic.  The phase offset `+ 0.8` ensures the two waves are not
in phase at `t = 0`, avoiding a sharp snap at startup.

The amplitude weights `0.6` and `0.4` sum to 1.0, so the total range stays
within `±BOAT_BOB_AMPLITUDE`.

**Why `state.last_frame` instead of a dedicated time accumulator?**  
`last_frame` is the wall-clock time since program start (set by
`state.last_frame = glfw.get_time()` each frame).  Using it as `t` means the
bob frequency is anchored to real time and won't accumulate floating-point
drift from summing `delta_time` repeatedly.

---

## 11. Bow Spray Particles

When the boat moves forward, two particle emitters at the bow produce
spray that flies outward to the sides and slightly backward – like water
pushed apart by a ship's prow.

### Computing the velocity vectors

```python
angle_rad = math.radians(state.boat_angle)
lat  = self.BOW_SPRAY_SPEED     # sideways component (2 units/s)
bwd  = self.BOW_BACKWARD_SPEED  # backward component (2 units/s)

right = [
     math.cos(angle_rad) * lat - math.sin(angle_rad) * bwd,
     0.0,
    -math.sin(angle_rad) * lat - math.cos(angle_rad) * bwd,
]
left = [
    -math.cos(angle_rad) * lat - math.sin(angle_rad) * bwd,
     0.0,
     math.sin(angle_rad) * lat - math.cos(angle_rad) * bwd,
]
```

This is **not** a sine wave – it is a 2D vector rotation.  The boat's local
axes are:
- **Forward** (local +Z) → world `(sin(angle), 0, cos(angle))`
- **Right**   (local +X) → world `(cos(angle), 0, -sin(angle))`

The right-spray velocity is: `+lateral × right_hat − backward × forward_hat`.
The left-spray velocity is:  `−lateral × right_hat − backward × forward_hat`.

Both velocities point away from the centerline and slightly backward, which
matches the wake of a moving vessel.

These vectors are recomputed every frame, so when the player turns, the
spray immediately adapts to the new heading.

---

## 12. The Particle System

### Data layout

Each active particle is a 7-element list:

```
[x, y, z,   age,   vx, vy, vz]
  position   time   velocity
```

### Update loop

```python
dampen = 1.0 - self.drag * dt
for p in self._particles:
    p[4] *= dampen   # apply drag to velocity
    p[5] *= dampen
    p[6] *= dampen
    p[0] += p[4] * dt   # integrate position
    p[1] += p[5] * dt
    p[2] += p[6] * dt
    p[3] += dt           # age the particle
```

This is **Euler integration**: `position += velocity × dt`.  Good enough for
short-lived visual effects where precision is not critical.

**Drag** exponentially decays the velocity:
after `n` frames with `drag = 1.0` and `dt ≈ 0.016`,
`dampen ≈ 0.984`, so velocity ≈ 0 after ~90 frames (1.5 seconds).
The bow spray uses drag so particles slow to a stop rather than flying away forever.

### Spawning

```python
self._spawn_acc += dt * self.spawn_rate
while self._spawn_acc >= 1.0:
    self._particles.append([*self.base_pos, 0.0, *self.velocity])
    self._spawn_acc -= 1.0
```

`spawn_rate` is "particles per second".  Instead of checking "is it time for
a new particle?" with wall-clock timestamps, the code accumulates fractional
particles as a running total.  Each time the total reaches 1.0, one particle
is born and 1.0 is subtracted.  This correctly handles varying `dt` values
without bunching or skipping.

### Drawing

Each particle is drawn as a **sphere** (the same UV sphere built by
`make_sphere`, already in the GPU buffer) scaled by its remaining life:

```python
t = p[3] / self.lifetime          # 0 at birth → 1 at death
scale = self.max_scale * (1.0 - t)  # shrinks to 0 at death
```

A particle is born at full size and shrinks to nothing as it dies.  No
blending/transparency is needed: the particle just becomes invisible by
collapsing to zero scale.

### Moving emitters

`base_pos` and `velocity` are mutable attributes updated every frame from
`scene.py`.  The chimney smoke emitter, for example, is repositioned to
follow the boat:

```python
self.boat_smoke.base_pos = list(
    self._local_to_world(self.CHIMNEY_TOP_LOCAL, s, state.boat_angle, ...)
)
```

Particles that were already spawned keep their own `(x, y, z, vx, vy, vz)` –
they have left the emitter and travel independently.  Only newly spawned
particles inherit the current `base_pos` and `velocity`.

---

## 13. Circular Orbits – Sharks, Horizon Boats, Sun Spin

All three share the same pattern: an angle accumulates over time, and
`sin/cos` map it to a position on a circle.

```python
# main_scene.py
state.shark_angle += scene.SHARK_SPEED * state.delta_time  # °/s

# scene.py – draw_sharks
orbit_rad = math.radians(orbit_deg)
x = center_x + RADIUS * math.sin(orbit_rad)
z = center_z + RADIUS * math.cos(orbit_rad)
```

### Why `sin` for X and `cos` for Z?

In this scene's convention, Z is "depth" (the axis going away from the
camera) and X is "sideways".  Starting at `angle = 0`:
- `sin(0) = 0` → X = 0 (centered)
- `cos(0) = 1` → Z = +RADIUS (ahead)

As the angle grows, the object traces a circle in the XZ plane (the ocean
floor), which is exactly what we want.

### Evenly distributing multiple orbiters

Each object gets a fixed phase offset so they start evenly spaced:

```python
orbit_deg = state.shark_angle + i * (360.0 / self.SHARK_COUNT)
```

With `SHARK_COUNT = 3`: offsets are 0°, 120°, 240°.  They all rotate at
the same speed (same `state.shark_angle`), so the spacing is permanently
preserved.

### Horizon boats face the direction of travel

A boat sailing along a circle should point along the **tangent** to that
circle, not toward the center.  The tangent direction is 90° ahead of the
radial direction:

```python
facing = 90.0 + orbit_deg
```

The model matrix then applies this Y-rotation, so the boat's nose always
points in its direction of motion.

---

## 14. The Rendering Pipeline End-to-End

Here is the full journey of one vertex from Python list to pixel:

```
geometry.py (import time)
  └─ vertices_list.append([x, y, z])   ← all geometry collected

main_scene.py (startup)
  └─ np.array → glBufferData           ← one upload to GPU

render loop (every frame, ~16ms at 60 FPS):
  │
  ├─ state.delta_time updated
  ├─ input processed → state mutated (boat_angle, boat_x, ...)
  ├─ autonomous angles updated (shark_angle, sun_spin, ...)
  │
  ├─ glClear
  │
  ├─ scene.draw_all()
  │     │
  │     ├─ for each object:
  │     │     glUniform4f(loc_color, r, g, b, a)      ← CPU → GPU (color)
  │     │     glUniformMatrix4fv(loc_model, ..., mat) ← CPU → GPU (model matrix)
  │     │     glDrawArrays(GL_TRIANGLES, start, count)
  │     │           │
  │     │           └─ vertex shader (runs on GPU, once per vertex):
  │     │                 gl_Position = projection * view * model * vec4(pos, 1.0)
  │     │
  │     └─ fragment shader (runs on GPU, once per pixel fragment):
  │           gl_FragColor = color   ← same color for every pixel of the object
  │
  └─ glfw.swap_buffers  ← show completed frame
```

### Why flat shading (uniform color)?

The fragment shader ignores normals and lighting entirely – every triangle of
an object gets one color.  This is the simplest possible shader and is a
deliberate scope choice for the assignment.  Adding Phong shading would require
uploading normals, computing `dot(normal, lightDir)`, etc.

### Why `glEnable(GL_DEPTH_TEST)`?

Without depth testing, the last object drawn wins every pixel, regardless of
whether it is behind or in front of other objects.  The depth buffer records
the closest Z value seen so far at each pixel; a new fragment is only written
if its Z is smaller (closer to the camera).  This is what makes the island
occlude the sea and the boat sit on top of the water correctly.

---

*Document written for SCC0250 – Computação Gráfica (2026), ICMC-USP.*  
*Authors: Laura Fernandes Camargos (13692334), Vitor Hugo Almeida Couto (13672787).*
