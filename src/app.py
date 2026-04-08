from dataclasses import dataclass


@dataclass
class AppState:
    """Minimal application-level config shared across module boundaries.

    Only values that genuinely cross the input/scene boundary and have no
    other clean home belong here.  Per-object state (boat position, sun spin,
    coqueiro scale) lives on the objects themselves; per-frame timing (dt) is
    passed explicitly as a function argument.
    """

    width: int = 960
    height: int = 720
    wireframe: bool = False
