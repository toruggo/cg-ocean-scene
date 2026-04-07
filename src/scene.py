from OpenGL.GL import *
import glm
import math
import numpy as np

from . import state
from . import geometry
from .particles import ParticleEmitter


model_matrix = geometry.model_matrix


class Scene:

    # ── Sea ───────────────────────────────────────────────────────────────────

    SEA_SX = 40.0
    SEA_SZ = 50.0

    # ── Island ────────────────────────────────────────────────────────────────
    #
    #   island1.obj  Y: -0.559 → 0.857  lift by 0.559, top at 1.416

    ISLAND_SCALE = 1.5
    ISLAND_POS = (-7.0, 1.5 * 0.559, -6.0)  # ty keeps base at y=0

    # ── Lighthouse ────────────────────────────────────────────────────────────
    #
    #   lighthouse.obj  Y: 0.000 → 9.802  place on island top

    LIGHTHOUSE_SCALE = 0.3
    LIGHTHOUSE_POS = (-7.0, 1.5 * 1.416, -6.0)  # on scaled island top

    LH_PART_COLORS = {
        "lighthouse_body": (0.980, 0.361, 0.361, 1.0),  # rgb(250,  92,  92)
        "Cylinder.001": (0.992, 0.541, 0.420, 1.0),  # rgb(253, 138, 107)
        "lighthouse_top_floor": (0.996, 0.761, 0.533, 1.0),  # rgb(254, 194, 136)
        "lighthouse_light": (0.984, 0.937, 0.463, 1.0),  # #FBEF76
    }

    # ── Coqueiros ─────────────────────────────────────────────────────────────
    #
    #   Scale driven at runtime by state.coqueiro_scale (Z/X keys).
    #   Each entry: (pos, y_angle, x_tilt)

    COQUEIROS = [
        ((-9.300, 1.9984, -6.039), 2.3, 0.0),
        ((-6.989, 0.7717, -3.975), 27.0, 30.0),
        ((-10.566, 0.8390, -5.779), -75.8, 30.0),
    ]

    COQUEIRO_PART_COLORS = {
        "tronco": (0.42, 0.30, 0.20, 1.0),
        "folhas": (0.18, 0.62, 0.28, 1.0),
    }

    # ── Volcano ───────────────────────────────────────────────────────────────
    #
    #   volcano_rock.obj  Y: -1.363 → 5.598  lift by 1.363

    VOLCANO_POS = (7.0, 1.363, 5.0)

    # ── Sun ───────────────────────────────────────────────────────────────────

    SUN_POS = (20.0, 12.0, -15.0)
    SUN_SCALE = 2.0
    SUN_ROT_ANGLE = 90.0
    SUN_ROT_AXIS = (1.0, 0.0, 1.0)

    # ── Boat ──────────────────────────────────────────────────────────────────

    BOAT_SCALE = 0.6
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

    # ── Horizon boats ─────────────────────────────────────────────────────────

    HORIZON_BOAT_COUNT = 3
    HORIZON_BOAT_RADIUS = 40.0
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

    # ── Sharks ────────────────────────────────────────────────────────────────

    SHARK_COUNT = 3
    SHARK_CENTER = (0.0, 0.0, 0.0)
    SHARK_RADIUS = 3.0
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
                self.VOLCANO_POS[1] + 5.6,
                self.VOLCANO_POS[2],
            ),
            color=(0.30, 0.28, 0.28, 1.0),
            spawn_rate=0.3,
            lifetime=10.0,
            velocity=(0.0, 0.5, 0.0),
            max_scale=0.7,
        )

    # ── View / projection ─────────────────────────────────────────────────────

    def set_view_projection(self, mat_view, mat_proj):
        glUniformMatrix4fv(self.loc_view, 1, GL_TRUE, mat_view)
        glUniformMatrix4fv(self.loc_projection, 1, GL_TRUE, mat_proj)

    # ── Private helpers ───────────────────────────────────────────────────────

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

    def _draw_coqueiro_parts(self, mat):
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)
        for name, (start, count) in geometry.coqueiro_parts.items():
            color = self.COQUEIRO_PART_COLORS.get(name, (1.0, 1.0, 1.0, 1.0))
            glUniform4f(self.loc_color, *color)
            glDrawArrays(GL_TRIANGLES, start, count)

    # ── Draw functions ────────────────────────────────────────────────────────

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
        glUniform4f(self.loc_color, 0.25, 0.25, 0.30, 1.0)
        s = self.SHARK_FIN_SCALE
        for i in range(self.SHARK_COUNT):
            orbit_deg = state.shark_angle + i * (360.0 / self.SHARK_COUNT)
            orbit_rad = math.radians(orbit_deg)
            x = self.SHARK_CENTER[0] + self.SHARK_RADIUS * math.sin(orbit_rad)
            z = self.SHARK_CENTER[2] + self.SHARK_RADIUS * math.cos(orbit_rad)
            glUniformMatrix4fv(
                self.loc_model,
                1,
                GL_TRUE,
                model_matrix(
                    angle=orbit_deg,
                    ry=1.0,
                    tx=x,
                    ty=self.SHARK_CENTER[1],
                    tz=z,
                    sx=s,
                    sy=s,
                    sz=s,
                ),
            )
            glDrawArrays(GL_TRIANGLES, geometry.start_fin, geometry.count_fin)
            self.shark_trails[i].base_pos = [x, self.SHARK_CENTER[1], z]

    def draw_horizon_boats(self):
        s = self.HORIZON_BOAT_SCALE
        cx, _, cz = self.HORIZON_BOAT_CENTER
        for i in range(self.HORIZON_BOAT_COUNT):
            orbit_deg = state.horizon_boat_angle + i * (360.0 / self.HORIZON_BOAT_COUNT)
            orbit_rad = math.radians(orbit_deg)
            x = cx + self.HORIZON_BOAT_RADIUS * math.sin(orbit_rad)
            z = cz + self.HORIZON_BOAT_RADIUS * math.cos(orbit_rad)
            facing = 90.0 + orbit_deg  # tangent of CCW orbit
            mat = model_matrix(
                angle=facing, ry=1.0, tx=x, ty=0.4, tz=z, sx=s, sy=s, sz=s
            )
            glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)
            for name, (start, count) in geometry.boat_parts.items():
                color = self.HORIZON_BOAT_PART_COLORS.get(name, (1.0, 1.0, 1.0, 1.0))
                glUniform4f(self.loc_color, *color)
                glDrawArrays(GL_TRIANGLES, start, count)

            self.horizon_boat_smokes[i].base_pos = list(
                self._local_to_world(
                    self.CHIMNEY_TOP_LOCAL,
                    s,
                    facing,
                    x,
                    0.4,
                    z,
                )
            )

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
            self._draw_coqueiro_parts(np.array(m))

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
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)
        for name, (start, count) in geometry.lh_parts.items():
            color = self.LH_PART_COLORS.get(name, (1.0, 1.0, 1.0, 1.0))
            glUniform4f(self.loc_color, *color)
            glDrawArrays(GL_TRIANGLES, start, count)

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
        s = self.BOAT_SCALE
        t = self.BOAT_BOB_SPEED * state.last_frame
        bob = self.BOAT_BOB_AMPLITUDE * (
            0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8)
        )
        mat = model_matrix(
            angle=state.boat_angle,
            ry=1.0,
            tx=state.boat_x,
            ty=0.4 + bob,
            tz=state.boat_z,
            sx=s,
            sy=s,
            sz=s,
        )
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)
        for name, (start, count) in geometry.boat_parts.items():
            color = self.BOAT_PART_COLORS.get(name, (1.0, 1.0, 1.0, 1.0))
            glUniform4f(self.loc_color, *color)
            glDrawArrays(GL_TRIANGLES, start, count)

        self.boat_smoke.base_pos = list(
            self._local_to_world(
                self.CHIMNEY_TOP_LOCAL,
                s,
                state.boat_angle,
                state.boat_x,
                0.4 + bob,
                state.boat_z,
            )
        )

        angle_rad = math.radians(state.boat_angle)
        wx3, wy3, wz3 = self._local_to_world(
            self.BOW_LOCAL,
            s,
            state.boat_angle,
            state.boat_x,
            0.4 + bob,
            state.boat_z,
        )
        # Spray = sideways + backward (backward = -heading = (-sin θ, 0, -cos θ))
        ss = self.BOW_SPRAY_SPEED
        sb = self.BOW_BACKWARD_SPEED
        right = [
            math.cos(angle_rad) * ss - math.sin(angle_rad) * sb,
            0.0,
            -math.sin(angle_rad) * ss - math.cos(angle_rad) * sb,
        ]
        left = [
            -math.cos(angle_rad) * ss - math.sin(angle_rad) * sb,
            0.0,
            math.sin(angle_rad) * ss - math.cos(angle_rad) * sb,
        ]
        self.bow_port.base_pos = [wx3, wy3, wz3]
        self.bow_port.velocity = left
        self.bow_starboard.base_pos = [wx3, wy3, wz3]
        self.bow_starboard.velocity = right

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
