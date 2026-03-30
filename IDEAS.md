# Scene Ideas & Experiments

## Colouring techniques (no textures)

### A — Per-vertex colour attribute
Add an RGBA colour alongside each position in the VBO. The GPU interpolates
colours across triangles automatically (Gouraud shading).

- Expand VBO layout to `(position, color)`
- Vertex shader: `attribute vec4 vColor; varying vec4 fColor;`
- Fragment shader: `gl_FragColor = fColor;`
- Gives smooth gradients between vertices (e.g. island sandy base → green top)
- Downside: OBJ loader must assign colours per vertex at load time

### B — Procedural colour in fragment shader
Compute colour from the fragment's interpolated position — no extra CPU data.

Examples:
- Height gradient: `mix(sandColor, grassColor, clamp(worldY / maxH, 0, 1))`
- Stripes: `fract(pos.x * freq) > 0.5 ? colorA : colorB`
- Radial pattern (good for the sun: dark centre → bright rim)

Requires passing vertex position as a `varying` to the fragment shader.
Patterns are in object/world space so they "swim" if computed in world space —
prefer local space for static patterns.

### C — Sub-mesh groups (multi-draw per object) ← current plan for boat & lighthouse
Split one logical object into named parts in Blender (`P → Separate`), export
with "Objects as OBJ Objects". Each `o PartName` block in the OBJ becomes its
own `(start, count)` slice; draw each with a different `uniform vec4 color`.

No shader changes required. Best for clean solid-colour parts (lighthouse
stripes, boat hull vs. sail vs. mast).

---

## Other scene ideas

- **Animated water**: offset sea vertices each frame using a sine wave on Y
  (needs dynamic VBO or vertex shader time uniform)
- **Day/night cycle**: lerp sky clear colour and object colours over time via
  a `u_time` uniform
- **Fog effect**: in fragment shader, lerp fragment colour toward sky colour
  based on distance from camera (`gl_FragCoord.z` or a passed depth)
- **Second island with coconut tree**: Island 2 + coconut.obj scaled via I/K
  keys (planned in assignment)
- **Volcano smoke**: particle system using small procedural quads emitted
  upward from volcano tip
