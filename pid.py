from typing import Tuple
def pid_step(error: float, dt: float, kp: float, ki: float, kd: float, integral: float, last_error: float, integ_limit: float) -> Tuple[float, float]:
    integral = max(-integ_limit, min(integ_limit, integral + error * dt))
    derivative = (error - last_error) / dt if dt > 0 else 0.0
    output = kp * error + ki * integral + kd * derivative
    return output, integral
