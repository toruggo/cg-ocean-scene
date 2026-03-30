from OpenGL.GL import *
import glm
import math
import numpy as np

import state
import geometry


def model_matrix(angle=0.0, rx=0.0, ry=1.0, rz=0.0,
                 tx=0.0, ty=0.0, tz=0.0,
                 sx=1.0, sy=1.0, sz=1.0):
    m = glm.mat4(1.0)
    m = glm.translate(m, glm.vec3(tx, ty, tz))
    if angle != 0.0:
        m = glm.rotate(m, math.radians(angle), glm.vec3(rx, ry, rz))
    m = glm.scale(m, glm.vec3(sx, sy, sz))
    return np.array(m)


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

    def __init__(self, program):
        self.loc_color      = glGetUniformLocation(program, "color")
        self.loc_model      = glGetUniformLocation(program, "model")
        self.loc_view       = glGetUniformLocation(program, "view")
        self.loc_projection = glGetUniformLocation(program, "projection")

    # ── View / projection ─────────────────────────────────────────────────────

    def set_view_projection(self, mat_view, mat_proj):
        glUniformMatrix4fv(self.loc_view,       1, GL_TRUE, mat_view)
        glUniformMatrix4fv(self.loc_projection, 1, GL_TRUE, mat_proj)

    # ── Draw functions ────────────────────────────────────────────────────────

    def draw_boat(self):
        glUniform4f(self.loc_color, 0.55, 0.27, 0.07, 1.0)
        s = self.BOAT_SCALE
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE,
            model_matrix(angle=state.boat_angle, ry=1.0,
                         tx=state.boat_x, ty=0.4, tz=state.boat_z,
                         sx=s, sy=s, sz=s))
        glDrawArrays(GL_TRIANGLES, geometry.start_boat, geometry.count_boat)

    def draw_island(self):
        glUniform4f(self.loc_color, 0.76, 0.70, 0.50, 1.0)
        s = self.ISLAND_SCALE
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE,
            model_matrix(tx=self.ISLAND_POS[0], ty=self.ISLAND_POS[1], tz=self.ISLAND_POS[2],
                         sx=s, sy=s, sz=s))
        glDrawArrays(GL_TRIANGLES, geometry.start_island, geometry.count_island)

    def draw_lighthouse(self):
        glUniform4f(self.loc_color, 0.95, 0.95, 0.92, 1.0)
        s = self.LIGHTHOUSE_SCALE
        glUniformMatrix4fv(self.loc_model, 1, GL_TRUE,
            model_matrix(tx=self.LIGHTHOUSE_POS[0], ty=self.LIGHTHOUSE_POS[1], tz=self.LIGHTHOUSE_POS[2],
                         sx=s, sy=s, sz=s))
        glDrawArrays(GL_TRIANGLES, geometry.start_lh, geometry.count_lh)

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
