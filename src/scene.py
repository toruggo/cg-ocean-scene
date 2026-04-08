from OpenGL.GL import *
import glm
import math
import numpy as np

from . import state
from . import geometry
from .particles import ParticleEmitter


model_matrix = geometry.model_matrix


class Scene:

    SEA_SX = 40.0  # world units
    SEA_SZ = 50.0  # world units

    ISLAND_SCALE = 1.5
    ISLAND_POS = (
        -7.0,
        1.5 * 0.559,
        -6.0,
    )  # ty = scale x model min-Y, lifts base to y=0

    LIGHTHOUSE_SCALE = 0.3
    LIGHTHOUSE_POS = (-7.0, 1.5 * 1.416, -6.0)  # ty = island scale x island top height

    LH_PART_COLORS = {
        "lighthouse_body": (0.980, 0.361, 0.361, 1.0),  # #FA5C5C
        "Cylinder.001": (0.992, 0.541, 0.420, 1.0),  # #FD8A6B
        "lighthouse_top_floor": (0.996, 0.761, 0.533, 1.0),  # #FEC288
        "lighthouse_light": (0.984, 0.937, 0.463, 1.0),  # #FBEF76
    }

    # Each entry: (pos, y_angle, x_tilt); scale driven at runtime by state.coqueiro_scale
    COQUEIROS = [
        ((-9.300, 1.9984, -6.039), 2.3, 0.0),
        ((-6.989, 0.7717, -3.975), 27.0, 30.0),
        ((-10.566, 0.8390, -5.779), -75.8, 30.0),
    ]

    COQUEIRO_PART_COLORS = {
        "tronco": (0.42, 0.30, 0.20, 1.0),
        "folhas": (0.18, 0.62, 0.28, 1.0),
    }

    VOLCANO_POS = (7.0, 1.363, 5.0)  # ty = model min-Y, lifts base to y=0

    SUN_POS = (20.0, 12.0, -15.0)
    SUN_SCALE = 2.0
    SUN_ROT_ANGLE = 90.0
    SUN_ROT_AXIS = (1.0, 0.0, 1.0)

    BOAT_SCALE = 0.6
    BOAT_BASE_Y = 0.4  # resting waterline height, world units
    BOAT_BOB_AMPLITUDE = 0.10  # world units
    BOAT_BOB_SPEED = 1.5  # radians per second (primary wave)

    BOAT_PART_COLORS = {
        "boat_bottom": (1.000, 0.608, 0.000, 1.0),  # #FF9B00
        "boat_top": (0.922, 0.890, 0.537, 1.0),  # #EBE389
        "cabin": (1.000, 0.788, 0.000, 1.0),  # #FFC900
        "cabin_top": (1.000, 0.882, 0.000, 1.0),  # #FFE100
        "chimney": (1.000, 0.608, 0.000, 1.0),  # #FF9B00
    }

    # Chimney top in boat local space (max-Y centroid of chimney vertices)
    CHIMNEY_TOP_LOCAL = (-0.1220, 2.1067, -1.2967)

    # Bow (front of boat_bottom) in boat local space
    BOW_LOCAL = (0.0000, -0.6, 2.1089)  # lowered to waterline
    BOW_SPRAY_SPEED = 2  # sideways component, world units/s
    BOW_BACKWARD_SPEED = 2  # backward component, world units/s

    HORIZON_BOAT_COUNT = 3
    HORIZON_BOAT_RADIUS = 40.0  # world units
    HORIZON_BOAT_CENTER = (0.0, 0.0, 0.0)
    HORIZON_BOAT_SPEED = 2.0  # degrees per second
    HORIZON_BOAT_SCALE = 0.6 * 0.8

    HORIZON_BOAT_PART_COLORS = {
        "boat_bottom": (0.22, 0.22, 0.22, 1.0),
        "boat_top": (0.30, 0.30, 0.30, 1.0),
        "cabin": (0.28, 0.28, 0.28, 1.0),
        "cabin_top": (0.25, 0.25, 0.25, 1.0),
        "chimney": (0.18, 0.18, 0.18, 1.0),
    }

    SHARK_COUNT = 3
    SHARK_CENTER = (0.0, 0.0, 0.0)
    SHARK_RADIUS = 3.0  # world units
    SHARK_SPEED = 25.0  # degrees per second
    SHARK_FIN_SCALE = 0.6

    def __init__(self, program):
        self.loc_color = glGetUniformLocation(program, "color")
        self.loc_model = glGetUniformLocation(program, "model")
        self.loc_view = glGetUniformLocation(program, "view")
        self.loc_projection = glGetUniformLocation(program, "projection")

        self.boat_smoke = ParticleEmitter(
            base_pos=(0.0, 0.0, 0.0),
            color=(0.55, 0.55, 0.55, 1.0),
            spawn_rate=2.0,
            lifetime=2.0,
            velocity=(0.0, 1.2, 0.0),
            max_scale=0.12,
        )
        # Bow spray: two emitters at boat front, base_pos and velocity
        # updated each frame to match the boat's current heading
        self.bow_port = ParticleEmitter(
            base_pos=(0.0, 0.0, 0.0),
            color=(0.90, 0.96, 1.0, 1.0),
            spawn_rate=5.0,
            lifetime=3,
            velocity=(0.0, 0.0, 0.0),
            max_scale=0.1,
            drag=1.0,
        )
        self.bow_starboard = ParticleEmitter(
            base_pos=(0.0, 0.0, 0.0),
            color=(0.90, 0.96, 1.0, 1.0),
            spawn_rate=5.0,
            lifetime=3,
            velocity=(0.0, 0.0, 0.0),
            max_scale=0.1,
            drag=1.0,
        )
        self.shark_trails = [
            ParticleEmitter(
                base_pos=(0.0, 0.0, 0.0),
                color=(0.75, 0.88, 1.0, 1.0),
                spawn_rate=8.0,
                lifetime=1.5,
                velocity=(0.0, 0.0, 0.0),
                max_scale=0.04,
            )
            for _ in range(self.SHARK_COUNT)
        ]
        self.horizon_boat_smokes = [
            ParticleEmitter(
                base_pos=(0.0, 0.0, 0.0),
                color=(0.60, 0.60, 0.65, 1.0),
                spawn_rate=1.5,
                lifetime=6.0,
                velocity=(0.0, 1.0, 0.0),
                max_scale=0.10,
            )
            for _ in range(self.HORIZON_BOAT_COUNT)
        ]
        self.volcano_smoke = ParticleEmitter(
            base_pos=(
                self.VOLCANO_POS[0],
                self.VOLCANO_POS[1] + 5.6,  # crater top offset in model space
                self.VOLCANO_POS[2],
            ),
            color=(0.30, 0.28, 0.28, 1.0),
            spawn_rate=0.3,
            lifetime=10.0,
            velocity=(0.0, 0.5, 0.0),
            max_scale=0.7,
        )

    # View / projection

    def set_view_projection(self, mat_view, mat_proj):
        glUniformMatrix4fv(self.loc_view, 1, GL_TRUE, mat_view)
        glUniformMatrix4fv(self.loc_projection, 1, GL_TRUE, mat_proj)

    # Private helpers

    @staticmethod
    def _local_to_world(local, scale, angle_deg, tx, ty, tz):
        """Transform a local-space point by uniform scale, Y-rotation, and translation."""
        lx, ly, lz = local
        sx, sy, sz = lx * scale, ly * scale, lz * scale
        a = math.radians(angle_deg)
        return (
            sx * math.cos(a) + sz * math.sin(a) + tx,
            sy + ty,
            -sx * math.sin(a) + sz * math.cos(a) + tz,
        )

    @staticmethod
    def _orbit_instances(count, center, radius, base_angle):
        """Yield (x, z, orbit_deg) for each evenly-spaced instance around a circular orbit."""
        for i in range(count):
            deg = base_angle + i * (360.0 / count)
            rad = math.radians(deg)
            yield center[0] + radius * math.sin(rad), center[2] + radius * math.cos(rad), deg

    def _draw_parts(self, parts, colors, mat, default=(1.0, 1.0, 1.0, 1.0)):
        """Set the model matrix and draw each named part with its corresponding color."""
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)
        for name, (start, count) in parts.items():
            glUniform4f(self.loc_color, *colors.get(name, default))
            glDrawArrays(GL_TRIANGLES, start, count)

    def _update_emitter_positions(self):
        """Reposition all particle emitters to match the current frame's object transforms.

        Called once per frame before particle update/draw so that draw functions
        remain pure render operations with no state side effects.
        """
        # Boat: smoke from chimney top, bow spray from bow point
        s = self.BOAT_SCALE
        t = self.BOAT_BOB_SPEED * state.last_frame
        bob = self.BOAT_BOB_AMPLITUDE * (
            0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
        )
        self.boat_smoke.base_pos = list(
            self._local_to_world(
                self.CHIMNEY_TOP_LOCAL,
                s,
                state.boat_angle,
                state.boat_x,
                self.BOAT_BASE_Y + bob,
                state.boat_z,
            )
        )
        wx, wy, wz = self._local_to_world(
            self.BOW_LOCAL,
            s,
            state.boat_angle,
            state.boat_x,
            self.BOAT_BASE_Y + bob,
            state.boat_z,
        )
        angle_rad = math.radians(state.boat_angle)
        lat = self.BOW_SPRAY_SPEED
        bwd = self.BOW_BACKWARD_SPEED
        self.bow_port.base_pos = [wx, wy, wz]
        self.bow_port.velocity = [
            -math.cos(angle_rad) * lat - math.sin(angle_rad) * bwd,
            0.0,
            math.sin(angle_rad) * lat - math.cos(angle_rad) * bwd,
        ]
        self.bow_starboard.base_pos = [wx, wy, wz]
        self.bow_starboard.velocity = [
            math.cos(angle_rad) * lat - math.sin(angle_rad) * bwd,
            0.0,
            -math.sin(angle_rad) * lat - math.cos(angle_rad) * bwd,
        ]

        # Sharks: trail emitter follows each fin
        for i, (x, z, _) in enumerate(
            self._orbit_instances(
                self.SHARK_COUNT, self.SHARK_CENTER, self.SHARK_RADIUS, state.shark_angle
            )
        ):
            self.shark_trails[i].base_pos = [x, self.SHARK_CENTER[1], z]

        # Horizon boats: smoke emitter follows each chimney top
        s_hb = self.HORIZON_BOAT_SCALE
        for i, (x, z, deg) in enumerate(
            self._orbit_instances(
                self.HORIZON_BOAT_COUNT,
                self.HORIZON_BOAT_CENTER,
                self.HORIZON_BOAT_RADIUS,
                state.horizon_boat_angle,
            )
        ):
            self.horizon_boat_smokes[i].base_pos = list(
                self._local_to_world(
                    self.CHIMNEY_TOP_LOCAL, s_hb, 90.0 + deg, x, self.BOAT_BASE_Y, z
                )
            )

    def _update_and_draw_particles(self):
        self.boat_smoke.update(state.delta_time)
        self.boat_smoke.draw(self.loc_model, self.loc_color)
        self.bow_port.active = state.boat_moving_forward
        self.bow_starboard.active = state.boat_moving_forward
        self.bow_port.update(state.delta_time)
        self.bow_port.draw(self.loc_model, self.loc_color)
        self.bow_starboard.update(state.delta_time)
        self.bow_starboard.draw(self.loc_model, self.loc_color)
        for trail in self.shark_trails:
            trail.update(state.delta_time)
            trail.draw(self.loc_model, self.loc_color)
        for smoke in self.horizon_boat_smokes:
            smoke.update(state.delta_time)
            smoke.draw(self.loc_model, self.loc_color)
        self.volcano_smoke.update(state.delta_time)
        self.volcano_smoke.draw(self.loc_model, self.loc_color)

    # Draw functions

    def draw_sea(self):
        glUniform4f(self.loc_color, 0.05, 0.35, 0.65, 1.0)
        glUniformMatrix4fv(
            self.loc_model,
            1,
            GL_TRUE,
            model_matrix(sx=self.SEA_SX, sy=1.0, sz=self.SEA_SZ),
        )
        glDrawArrays(GL_TRIANGLES, geometry.start_sea, geometry.count_sea)

    def draw_sharks(self):
        """Draw SHARK_COUNT fins evenly distributed around a circular orbit.

        Each fin is rotated to face its direction of travel.
        """
        glUniform4f(self.loc_color, 0.25, 0.25, 0.30, 1.0)
        s = self.SHARK_FIN_SCALE
        for x, z, deg in self._orbit_instances(
            self.SHARK_COUNT, self.SHARK_CENTER, self.SHARK_RADIUS, state.shark_angle
        ):
            glUniformMatrix4fv(
                self.loc_model,
                1,
                GL_TRUE,
                model_matrix(
                    angle=deg, ry=1.0, tx=x, ty=self.SHARK_CENTER[1], tz=z,
                    sx=s, sy=s, sz=s,
                ),
            )
            glDrawArrays(GL_TRIANGLES, geometry.start_fin, geometry.count_fin)

    def draw_horizon_boats(self):
        """Draw HORIZON_BOAT_COUNT boats evenly distributed around a circular orbit.

        Each boat faces the tangent of its orbit so it appears to sail forward.
        """
        s = self.HORIZON_BOAT_SCALE
        for x, z, deg in self._orbit_instances(
            self.HORIZON_BOAT_COUNT,
            self.HORIZON_BOAT_CENTER,
            self.HORIZON_BOAT_RADIUS,
            state.horizon_boat_angle,
        ):
            mat = model_matrix(
                angle=90.0 + deg, ry=1.0, tx=x, ty=self.BOAT_BASE_Y, tz=z,
                sx=s, sy=s, sz=s,
            )
            self._draw_parts(geometry.boat_parts, self.HORIZON_BOAT_PART_COLORS, mat)

    def draw_sun(self):
        glUniform4f(self.loc_color, 1.0, 0.85, 0.10, 1.0)
        m = glm.mat4(1.0)
        m = glm.translate(m, glm.vec3(*self.SUN_POS))
        m = glm.rotate(
            m, math.radians(self.SUN_ROT_ANGLE), glm.vec3(*self.SUN_ROT_AXIS)
        )
        m = glm.rotate(m, math.radians(state.sun_spin), glm.vec3(0.0, 1.0, 0.0))
        m = glm.scale(m, glm.vec3(self.SUN_SCALE, self.SUN_SCALE, self.SUN_SCALE))
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, np.array(m))
        glDrawArrays(GL_TRIANGLES, geometry.start_sun, geometry.count_sun)

    def draw_island(self):
        glUniform4f(self.loc_color, 0.76, 0.70, 0.50, 1.0)
        s = self.ISLAND_SCALE
        glUniformMatrix4fv(
            self.loc_model,
            1,
            GL_TRUE,
            model_matrix(
                tx=self.ISLAND_POS[0],
                ty=self.ISLAND_POS[1],
                tz=self.ISLAND_POS[2],
                sx=s,
                sy=s,
                sz=s,
            ),
        )
        glDrawArrays(GL_TRIANGLES, geometry.start_island, geometry.count_island)

    def draw_coqueiro(self):
        s = state.coqueiro_scale
        for pos, angle, tilt in self.COQUEIROS:
            tx, ty, tz = pos
            m = glm.mat4(1.0)
            m = glm.translate(m, glm.vec3(tx, ty, tz))
            m = glm.rotate(m, math.radians(angle), glm.vec3(0, 1, 0))
            m = glm.rotate(m, math.radians(tilt), glm.vec3(1, 0, 0))
            m = glm.scale(m, glm.vec3(s, s, s))
            self._draw_parts(geometry.coqueiro_parts, self.COQUEIRO_PART_COLORS, np.array(m))

    def draw_lighthouse(self):
        s = self.LIGHTHOUSE_SCALE
        mat = model_matrix(
            tx=self.LIGHTHOUSE_POS[0],
            ty=self.LIGHTHOUSE_POS[1],
            tz=self.LIGHTHOUSE_POS[2],
            sx=s,
            sy=s,
            sz=s,
        )
        self._draw_parts(geometry.lh_parts, self.LH_PART_COLORS, mat)

    def draw_volcano(self):
        glUniform4f(self.loc_color, 0.35, 0.30, 0.28, 1.0)
        glUniformMatrix4fv(
            self.loc_model,
            1,
            GL_TRUE,
            model_matrix(
                tx=self.VOLCANO_POS[0], ty=self.VOLCANO_POS[1], tz=self.VOLCANO_POS[2]
            ),
        )
        glDrawArrays(GL_TRIANGLES, geometry.start_volcano, geometry.count_volcano)

    def draw_boat(self):
        """Draw the player boat with a bobbing animation.

        Computes a bob offset from a two-frequency sine wave and applies it to the
        model matrix.
        """
        s = self.BOAT_SCALE
        t = self.BOAT_BOB_SPEED * state.last_frame
        # sum of two sine waves at different frequencies for a natural-looking bob
        bob = self.BOAT_BOB_AMPLITUDE * (
            0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
        )
        mat = model_matrix(
            angle=state.boat_angle,
            ry=1.0,
            tx=state.boat_x,
            ty=self.BOAT_BASE_Y + bob,
            tz=state.boat_z,
            sx=s,
            sy=s,
            sz=s,
        )
        self._draw_parts(geometry.boat_parts, self.BOAT_PART_COLORS, mat)

    def draw_all(self):
        self.draw_sea()
        self.draw_sharks()
        self.draw_horizon_boats()
        self.draw_sun()
        self.draw_island()
        self.draw_coqueiro()
        self.draw_lighthouse()
        self.draw_volcano()
        self.draw_boat()
        self._update_emitter_positions()
        self._update_and_draw_particles()
