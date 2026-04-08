from OpenGL.GL import *

from . import geometry
from .geometry import model_matrix


class ParticleEmitter:
    def __init__(
        self,
        base_pos,
        color=(0.5, 0.5, 0.5, 1.0),
        spawn_rate=2.0,
        lifetime=2.0,
        velocity=(0.0, 1.0, 0.0),
        max_scale=0.15,
        drag=0.0,
    ):
        """
        base_pos   -- (x, y, z) world-space spawn point; update each frame for moving emitters
        spawn_rate -- particles per second
        lifetime   -- seconds each particle lives
        velocity   -- (vx, vy, vz) world-space units per second; update each frame for
                      direction-dependent emitters (e.g. bow spray)
        max_scale  -- sphere radius at birth; shrinks to 0 at end of lifetime
        """
        self.base_pos = list(base_pos)
        self.color = color
        self.spawn_rate = spawn_rate
        self.lifetime = lifetime
        self.velocity = list(velocity)
        self.max_scale = max_scale
        self.drag = drag
        self.active = (
            True  # set False to pause spawning; existing particles still finish
        )
        self.anchor = None  # local-space offset; set by owner when needed

        self._particles = []  # each entry: [x, y, z, age, vx, vy, vz]
        self._spawn_acc = 0.0

    def update(self, dt):
        if self.active:
            self._spawn_acc += dt * self.spawn_rate
            while self._spawn_acc >= 1.0:
                self._particles.append([*self.base_pos, 0.0, *self.velocity])
                self._spawn_acc -= 1.0

        dampen = 1.0 - self.drag * dt
        for p in self._particles:
            p[4] *= dampen
            p[5] *= dampen
            p[6] *= dampen
            p[0] += p[4] * dt
            p[1] += p[5] * dt
            p[2] += p[6] * dt
            p[3] += dt

        self._particles = [p for p in self._particles if p[3] < self.lifetime]

    def draw(self, loc_model, loc_color):
        glUniform4f(loc_color, *self.color)
        for p in self._particles:
            t = p[3] / self.lifetime
            scale = self.max_scale * (1.0 - t)
            glUniformMatrix4fv(
                loc_model,
                1,
                GL_TRUE,
                model_matrix(tx=p[0], ty=p[1], tz=p[2], sx=scale, sy=scale, sz=scale),
            )
            glDrawArrays(GL_TRIANGLES, geometry.start_particle, geometry.count_particle)
