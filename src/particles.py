import math
from OpenGL.GL import *

from . import geometry
from .geometry import model_matrix


class ParticleEmitter:
    def __init__(self, base_pos,
                 color=(0.5, 0.5, 0.5, 1.0),
                 spawn_rate=2.0,
                 lifetime=2.0,
                 rise_speed=1.0,
                 max_scale=0.15):
        """
        base_pos   -- (x, y, z) world-space spawn point; update each frame for moving emitters
        spawn_rate -- particles per second
        lifetime   -- seconds each particle lives
        rise_speed -- world units per second upward
        max_scale  -- sphere radius at birth; shrinks to 0 at end of lifetime
        """
        self.base_pos   = list(base_pos)
        self.color      = color
        self.spawn_rate = spawn_rate
        self.lifetime   = lifetime
        self.rise_speed = rise_speed
        self.max_scale  = max_scale

        self._particles  = []   # each entry: [x, y, z, age]
        self._spawn_acc  = 0.0  # fractional particle accumulator

    def update(self, dt):
        self._spawn_acc += dt * self.spawn_rate
        while self._spawn_acc >= 1.0:
            self._particles.append([*self.base_pos, 0.0])
            self._spawn_acc -= 1.0

        for p in self._particles:
            p[1] += self.rise_speed * dt
            p[3] += dt

        self._particles = [p for p in self._particles if p[3] < self.lifetime]

    def draw(self, loc_model, loc_color):
        glUniform4f(loc_color, *self.color)
        for p in self._particles:
            t     = p[3] / self.lifetime          # 0 → 1
            scale = self.max_scale * (1.0 - t)
            glUniformMatrix4fv(loc_model, 1, GL_TRUE,
                model_matrix(tx=p[0], ty=p[1], tz=p[2],
                             sx=scale, sy=scale, sz=scale))
            glDrawArrays(GL_TRIANGLES,
                         geometry.start_particle,
                         geometry.count_particle)
