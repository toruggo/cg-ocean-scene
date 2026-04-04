# Ocean Scene — CG Projeto 1

An interactive 3D/2D ocean scene built with modern OpenGL (Python). A boat navigates the sea around islands, a lighthouse, a coconut tree, a volcano, orbiting sharks, drifting clouds, and a spinning sun — all rendered from a fixed bird's-eye camera.

---

## Setup

**Requirements:** Python 3.10+

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate     # Linux / macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python projeto1.py
```

---

## Controls

| Key | Action |
|-----|--------|
| W / S | Move boat forward / backward |
| A / D | Rotate boat left / right |
| I / K | Scale coconut tree up / down |
| P | Toggle wireframe mode |
| ESC | Close window |

---

## Project Structure

```
.
├── projeto1.py          # Entry point — window, shader setup, VBO upload, render loop
│
├── src/                 # Application modules
│   ├── state.py         # Global mutable state (camera, boat position, timing, toggles)
│   ├── geometry.py      # Vertex data builders for all scene objects + model_matrix helper
│   ├── scene.py         # Scene class — draws every object each frame using state + geometry
│   ├── particles.py     # Particle emitter (volcano smoke, boat wake)
│   ├── input.py         # GLFW keyboard/mouse callbacks
│   └── shader_s.py      # Shader loader/compiler wrapper
│
├── shaders/
│   ├── vertex_shader.vs
│   └── fragment_shader.fs
│
├── models/              # OBJ meshes loaded at startup
│   ├── barco.obj
│   ├── lighthouse.obj
│   ├── island1.obj
│   ├── volcano_rock.obj
│   └── coqueiro_separado.obj
│
└── requirements.txt
```

### Module responsibilities

- **`projeto1.py`** bootstraps everything: initialises GLFW, compiles shaders, calls `geometry` to build all vertex data, uploads the single shared VBO, then runs the render loop calling `scene.draw()` each frame.
- **`src/state.py`** is the single source of truth for runtime values (boat position, shark angle, sun spin, camera matrices). All other modules import from it rather than passing arguments around.
- **`src/geometry.py`** contains pure functions that return `np.float32` vertex arrays for every object (procedural shapes and OBJ-loaded meshes). It also exposes `model_matrix()`, a thin GLM helper used throughout.
- **`src/scene.py`** holds the `Scene` class, which issues all `glDrawArrays` calls, sets per-object `color` uniforms, and applies model transforms. It reads from `state` and calls into `geometry` for dynamic transforms.
- **`src/particles.py`** implements a `ParticleEmitter` that spawns, ages, and draws billboard particles (volcano smoke, boat movement wake).
- **`src/input.py`** registers GLFW callbacks and writes back into `state` (keys held, wireframe toggle, free-camera movement when enabled).
