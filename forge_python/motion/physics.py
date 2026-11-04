"""Reusable non-linear motion and continuous micro-drift."""
import numpy as np
from scipy.integrate import solve_ivp

def spring(times, damping=0.8, frequency=10):
    times = np.asarray(times, dtype=float)
    if times.ndim != 1 or not len(times) or np.any(times < 0) or np.any(np.diff(times) <= 0):
        raise ValueError('times must be a nonempty, strictly increasing nonnegative sequence')
    if times[-1] == 0: return np.array([0.0])
    solution = solve_ivp(lambda t, y: [y[1], frequency**2 * (1-y[0]) - 2*damping*frequency*y[1]], (0, times[-1]), [0, 0], t_eval=times, rtol=1e-7, atol=1e-9)
    return solution.y[0]

def drift(t):
    return {'x': 0.003*np.sin(0.37*t), 'y': 0.003*np.sin(0.29*t + 1), 'scale': 1 + 0.003*np.sin(0.23*t + 0.5)}
