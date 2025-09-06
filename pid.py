class PID:
    def __init__(self, kp, ki, kd, out_min=0.0, out_max=1.0):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.out_min, self.out_max = out_min, out_max
        self.i = 0.0
        self.prev_e = None

    def step(self, error, dt):
        p = self.kp * error
        self.i += self.ki * error * dt
        d = 0.0 if self.prev_e is None else self.kd * (error - self.prev_e) / max(dt, 1e-6)
        self.prev_e = error
        u = p + self.i + d
        return max(self.out_min, min(self.out_max, u))

def leverage_from_pid(u, lev_min, lev_max):
    return lev_min + u * (lev_max - lev_min)
