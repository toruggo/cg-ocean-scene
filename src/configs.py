"""Visual identity catalog — one ObjectConfig per distinct look.

Each entry declares only what an object *looks* like: which mesh slices to
draw and what color each part gets. Placement (pos, scale, rotations) belongs
on Transform instances in scene.py, not here.

PLAYER_BOAT and HORIZON_BOAT reference the same geometry (boat_parts) but
have different part_colors, illustrating that config is identity, not instance.
"""

from . import geometry
from .objects import ObjectConfig

SEA = ObjectConfig(
    default_color=(0.05, 0.35, 0.65, 1.0),
    geometry_range=(geometry.start_sea, geometry.count_sea),
)

ISLAND = ObjectConfig(
    default_color=(0.76, 0.70, 0.50, 1.0),
    geometry_range=(geometry.start_island, geometry.count_island),
)

VOLCANO = ObjectConfig(
    default_color=(0.35, 0.30, 0.28, 1.0),
    geometry_range=(geometry.start_volcano, geometry.count_volcano),
)

SUN = ObjectConfig(
    default_color=(1.0, 0.85, 0.10, 1.0),
    geometry_range=(geometry.start_sun, geometry.count_sun),
)

LIGHTHOUSE = ObjectConfig(
    geometry_parts=geometry.lh_parts,
    part_colors={
        "lighthouse_body":      (0.980, 0.361, 0.361, 1.0),
        "Cylinder.001":         (0.992, 0.541, 0.420, 1.0),
        "lighthouse_top_floor": (0.996, 0.761, 0.533, 1.0),
        "lighthouse_light":     (0.984, 0.937, 0.463, 1.0),
    },
)

COQUEIRO = ObjectConfig(
    geometry_parts=geometry.coqueiro_parts,
    part_colors={
        "tronco": (0.42, 0.30, 0.20, 1.0),
        "folhas": (0.18, 0.62, 0.28, 1.0),
    },
)

PLAYER_BOAT = ObjectConfig(
    geometry_parts=geometry.boat_parts,
    part_colors={
        "boat_bottom": (1.000, 0.608, 0.000, 1.0),
        "boat_top":    (0.922, 0.890, 0.537, 1.0),
        "cabin":       (1.000, 0.788, 0.000, 1.0),
        "cabin_top":   (1.000, 0.882, 0.000, 1.0),
        "chimney":     (1.000, 0.608, 0.000, 1.0),
    },
)

# Same mesh as PLAYER_BOAT; greyscale palette makes horizon boats look distant.
HORIZON_BOAT = ObjectConfig(
    geometry_parts=geometry.boat_parts,
    part_colors={
        "boat_bottom": (0.22, 0.22, 0.22, 1.0),
        "boat_top":    (0.30, 0.30, 0.30, 1.0),
        "cabin":       (0.28, 0.28, 0.28, 1.0),
        "cabin_top":   (0.25, 0.25, 0.25, 1.0),
        "chimney":     (0.18, 0.18, 0.18, 1.0),
    },
)

SHARK_FIN = ObjectConfig(
    default_color=(0.25, 0.25, 0.30, 1.0),
    geometry_range=(geometry.start_fin, geometry.count_fin),
)
