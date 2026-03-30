from OpenGL.GL import *
import glm
import math
import numpy as np

from . import state
from . import geometry
from .particles import ParticleEmitter


model_matrix = geometry.model_matrix


class Scene:
    # ── Placement & rendering constants ───────────────────────────────────────
    #
    #   island1.obj      Y: -0.559 →  0.857  lift by 0.559, top at 1.416
    #   lighthouse.obj   Y:  0.000 →  9.802  place on island top
    #   volcano_rock.obj Y: -1.363 →  5.598  lift by 1.363

    ISLAND_SCALE     = 1.5
    LIGHTHOUSE_SCALE = 0.3
    BOAT_SCALE       = 0.6

    ISLAND_POS     = (-7.0,  1.5 * 0.559, -6.0)   # ty keeps base at y=0
    LIGHTHOUSE_POS = (-7.0,  1.5 * 1.416, -6.0)   # on scaled island top
    VOLCANO_POS    = ( 7.0,  1.363,        5.0)

    SHARK_COUNT     = 3
    SHARK_CENTER    = (0.0, 0.0, 0.0)
    SHARK_RADIUS    = 3.0
    SHARK_SPEED     = 25.0   # degrees per second
    SHARK_FIN_SCALE = 0.6

    SEA_SX = 40.0
    SEA_SZ = 50.0

    SUN_POS       = (20.0, 12.0, -15.0)
    SUN_SCALE     = 2.0
    SUN_ROT_ANGLE = 90.0
    SUN_ROT_AXIS  = (1.0, 0.0, 1.0)

    CLOUD_ROT_ANGLE = 90.0
    CLOUD_ROT_AXIS  = (6.0, -2.0, 1.0)

    # Chimney top in boat local space (max-Y centroid of chimney vertices)
    CHIMNEY_TOP_LOCAL = (-0.1220, 2.1067, -1.2967)

    def __init__(self, program):
        self.loc_color      = glGetUniformLocation(program, "color")
        self.loc_model      = glGetUniformLocation(program, "model")
        self.loc_view       = glGetUniformLocation(program, "view")
        self.loc_projection = glGetUniformLocation(program, "projection")

        self.boat_smoke = ParticleEmitter(
            base_pos   = (0.0, 0.0, 0.0),   # updated each frame in draw_boat
            color      = (0.55, 0.55, 0.55, 1.0),
            spawn_rate = 2.0,
            lifetime   = 2.0,
            rise_speed = 1.2,
            max_scale  = 0.12,
        )
        self.volcano_smoke = ParticleEmitter(
            base_pos   = (self.VOLCANO_POS[0], self.VOLCANO_POS[1] + 5.6, self.VOLCANO_POS[2]),
            color      = (0.30, 0.28, 0.28, 1.0),
            spawn_rate = 1.0,
            lifetime   = 4.0,
            rise_speed = 0.5,
            max_scale  = 0.1,
        )

    # ── View / projection ─────────────────────────────────────────────────────

    def set_view_projection(self, mat_view, mat_proj):
        glUniformMatrix4fv(self.loc_view,       1, GL_TRUE, mat_view)
        glUniformMatrix4fv(self.loc_projection, 1, GL_TRUE, mat_proj)

    # ── Draw functions ────────────────────────────────────────────────────────

    BOAT_BOB_AMPLITUDE = 0.10   # world units
    BOAT_BOB_SPEED     = 1.5   # radians per second (primary wave)

    BOAT_PART_COLORS = {
        'boat_bottom': (0.8, 0.1, 0.1, 1.0),   # red
        'boat_top':    (0.1, 0.3, 0.9, 1.0),   # blue
        'cabin':       (0.1, 0.8, 0.1, 1.0),   # green
        'cabin_top':   (1.0, 0.9, 0.1, 1.0),   # yellow
        'chimney':     (0.9, 0.1, 0.9, 1.0),   # magenta
    }

    def draw_boat(self):
        s = self.BOAT_SCALE
        t = self.BOAT_BOB_SPEED * state.last_frame
        bob = self.BOAT_BOB_AMPLITUDE * (0.6 * math.sin(t) + 0.4 * math.sin(2.3 * t + 0.8))
        mat = model_matrix(angle=state.boat_angle, ry=1.0,
                           tx=state.boat_x, ty=0.4 + bob, tz=state.boat_z,
                           sx=s, sy=s, sz=s)
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)
        for name, (start, count) in geometry.boat_parts.items():
            color = self.BOAT_PART_COLORS.get(name, (1.0, 1.0, 1.0, 1.0))
            glUniform4f(self.loc_color, *color)
            glDrawArrays(GL_TRIANGLES, start, count)

        # Update boat smoke emitter to chimney top in world space
        lx, ly, lz = self.CHIMNEY_TOP_LOCAL
        angle_rad = math.radians(state.boat_angle)
        sx, sy, sz = lx * s, ly * s, lz * s
        wx =  sx * math.cos(angle_rad) + sz * math.sin(angle_rad) + state.boat_x
        wy =  sy + 0.4 + bob
        wz = -sx * math.sin(angle_rad) + sz * math.cos(angle_rad) + state.boat_z
        self.boat_smoke.base_pos = [wx, wy, wz]

    def draw_island(self):
        glUniform4f(self.loc_color, 0.76, 0.70, 0.50, 1.0)
        s = self.ISLAND_SCALE
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE,
            model_matrix(tx=self.ISLAND_POS[0], ty=self.ISLAND_POS[1], tz=self.ISLAND_POS[2],
                         sx=s, sy=s, sz=s))
        glDrawArrays(GL_TRIANGLES, geometry.start_island, geometry.count_island)

    LH_PART_COLORS = {
        'lighthouse_body':      (0.8, 0.1, 0.1, 1.0),   # red
        'Cylinder.001':         (0.1, 0.3, 0.9, 1.0),   # blue
        'lighthouse_top_floor': (0.1, 0.8, 0.1, 1.0),   # green
        'lighthouse_light':     (1.0, 0.9, 0.1, 1.0),   # yellow
    }

    def draw_lighthouse(self):
        s = self.LIGHTHOUSE_SCALE
        mat = model_matrix(tx=self.LIGHTHOUSE_POS[0], ty=self.LIGHTHOUSE_POS[1], tz=self.LIGHTHOUSE_POS[2],
                           sx=s, sy=s, sz=s)
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, mat)
        for name, (start, count) in geometry.lh_parts.items():
            color = self.LH_PART_COLORS.get(name, (1.0, 1.0, 1.0, 1.0))
            glUniform4f(self.loc_color, *color)
            glDrawArrays(GL_TRIANGLES, start, count)

    def draw_volcano(self):
        glUniform4f(self.loc_color, 0.35, 0.30, 0.28, 1.0)
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE,
            model_matrix(tx=self.VOLCANO_POS[0], ty=self.VOLCANO_POS[1], tz=self.VOLCANO_POS[2]))
        glDrawArrays(GL_TRIANGLES, geometry.start_volcano, geometry.count_volcano)

    def draw_sun(self):
        glUniform4f(self.loc_color, 1.0, 0.85, 0.10, 1.0)
        m = glm.mat4(1.0)
        m = glm.translate(m, glm.vec3(*self.SUN_POS))
        m = glm.rotate(m, math.radians(self.SUN_ROT_ANGLE), glm.vec3(*self.SUN_ROT_AXIS))
        m = glm.rotate(m, math.radians(state.sun_spin),     glm.vec3(0.0, 1.0, 0.0))
        m = glm.scale(m,  glm.vec3(self.SUN_SCALE, self.SUN_SCALE, self.SUN_SCALE))
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, np.array(m))
        glDrawArrays(GL_TRIANGLES, geometry.start_sun, geometry.count_sun)

    def draw_sharks(self):
        glUniform4f(self.loc_color, 0.25, 0.25, 0.30, 1.0)
        s = self.SHARK_FIN_SCALE
        for i in range(self.SHARK_COUNT):
            orbit_deg = state.shark_angle + i * (360.0 / self.SHARK_COUNT)
            orbit_rad = math.radians(orbit_deg)
            x = self.SHARK_CENTER[0] + self.SHARK_RADIUS * math.sin(orbit_rad)
            z = self.SHARK_CENTER[2] + self.SHARK_RADIUS * math.cos(orbit_rad)
            glUniformMatrix4fv(self.loc_model, 1, GL_TRUE,
                model_matrix(angle=orbit_deg, ry=1.0,
                             tx=x, ty=self.SHARK_CENTER[1], tz=z,
                             sx=s, sy=s, sz=s))
            glDrawArrays(GL_TRIANGLES, geometry.start_fin, geometry.count_fin)

    def draw_clouds(self):
        glUniform4f(self.loc_color, 1.0, 1.0, 1.0, 1.0)
        for i, (start, count) in enumerate(geometry.clouds):
            _, tx, ty, tz, *_ = geometry.CLOUD_DEFS[i]
            m = glm.mat4(1.0)
            m = glm.translate(m, glm.vec3(tx, ty, tz))
            m = glm.rotate(m, math.radians(self.CLOUD_ROT_ANGLE), glm.vec3(*self.CLOUD_ROT_AXIS))
            glUniformMatrix4fv(self.loc_model, 1, GL_TRUE, np.array(m))
            glDrawArrays(GL_TRIANGLES, start, count)

    def draw_sea(self):
        glUniform4f(self.loc_color, 0.05, 0.35, 0.65, 1.0)
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE,
            model_matrix(sx=self.SEA_SX, sy=1.0, sz=self.SEA_SZ))
        glDrawArrays(GL_TRIANGLES, geometry.start_sea, geometry.count_sea)

    def draw_all(self):
        self.draw_sea()
        self.draw_clouds()
        self.draw_sharks()
        self.draw_sun()
        self.draw_island()
        self.draw_lighthouse()
        self.draw_volcano()
        self.draw_boat()
        self.boat_smoke.update(state.delta_time)
        self.boat_smoke.draw(self.loc_model, self.loc_color)
        self.volcano_smoke.update(state.delta_time)
        self.volcano_smoke.draw(self.loc_model, self.loc_color)
