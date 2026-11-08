"""Capacity and delay formulas (vectorised).

Signalised nodes use the **critical lane volume** (CLV) method: per-lane flows are summed along
the critical path of the phasing and compared with a critical lane capacity (1,600 veh/h per
lane in FHWA Cap-X). Delay uses a Webster cycle and the HCM uniform and incremental delay
terms for the critical lane groups.

Roundabout entries use the **HCM 7 exponential entry capacity** models (passenger cars)::

    single-lane entry vs 1 circulating lane      c = 1380 exp(-1.02e-3 v_c)
    two-lane entry vs 2 circulating lanes: right c = 1420 exp(-0.85e-3 v_c)
                                           left  c = 1350 exp(-0.92e-3 v_c)

with the HCM roundabout control delay

``d = 3600/c + 900 T [ (x - 1) + sqrt((x - 1)^2 + (3600/c) x / (450 T)) ] + 5 min(x, 1)``.
"""

from __future__ import annotations

import numpy as np

CRITICAL_LANE_CAPACITY = 1600.0  # veh/h/ln (Cap-X)
SAT_FLOW = 1800.0  # veh/h/ln for Webster/HCM delay
LOST_PER_PHASE = 4.0  # s
T_ANALYSIS = 0.25  # h


def clv_vc(clv: np.ndarray) -> np.ndarray:
    return np.asarray(clv, float) / CRITICAL_LANE_CAPACITY


def signal_delay(phase_flows: list[np.ndarray], phase_lane_flows: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Average control delay (s/veh) and cycle (s) of a signalised node.

    Args:
        phase_flows: total vehicles served on each critical phase (veh/h).
        phase_lane_flows: critical lane flow of each phase (veh/h/ln).
    """
    n = len(phase_lane_flows)
    y = np.stack([np.asarray(f, float) / SAT_FLOW for f in phase_lane_flows])  # (phases, ...)
    big_y = y.sum(axis=0)
    lost = LOST_PER_PHASE * n
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(big_y < 0.95, (1.5 * lost + 5.0) / (1.0 - big_y), 150.0)
    c = np.clip(c, 50.0, 150.0)
    eff = c - lost
    tot_flow = np.zeros_like(big_y)
    tot_delay = np.zeros_like(big_y)
    for i in range(n):
        g = np.where(big_y > 0, eff * y[i] / np.where(big_y > 0, big_y, 1.0), eff / n)
        g = np.maximum(g, 5.0)
        g_c = g / c
        cap = SAT_FLOW * g_c
        x = np.where(cap > 0, np.asarray(phase_lane_flows[i], float) / cap, 0.0)
        d1 = 0.5 * c * (1 - g_c) ** 2 / (1 - np.minimum(x, 1.0) * g_c)
        d2 = 900 * T_ANALYSIS * ((x - 1) + np.sqrt((x - 1) ** 2 + 8 * 0.5 * x / (np.maximum(cap, 1.0) * T_ANALYSIS)))
        v = np.asarray(phase_flows[i], float)
        tot_flow = tot_flow + v
        tot_delay = tot_delay + v * (d1 + d2)
    return np.where(tot_flow > 0, tot_delay / np.where(tot_flow > 0, tot_flow, 1.0), 0.0), c


def rbt_capacity_single(vc: np.ndarray) -> np.ndarray:
    return 1380.0 * np.exp(-1.02e-3 * np.asarray(vc, float))


def rbt_capacity_two_lane(vc: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    vc = np.asarray(vc, float)
    return 1420.0 * np.exp(-0.85e-3 * vc), 1350.0 * np.exp(-0.92e-3 * vc)


def rbt_delay(v: np.ndarray, c: np.ndarray) -> np.ndarray:
    v = np.asarray(v, float)
    c = np.maximum(np.asarray(c, float), 1.0)
    x = v / c
    t = T_ANALYSIS
    return 3600.0 / c + 900.0 * t * ((x - 1) + np.sqrt((x - 1) ** 2 + (3600.0 / c) * x / (450.0 * t))) + 5.0 * np.minimum(x, 1.0)


def los_signalized(d: np.ndarray, vc: np.ndarray | None = None) -> np.ndarray:
    edges = np.array([10, 20, 35, 55, 80])
    letters = np.array(list("ABCDEF"))
    out = letters[np.searchsorted(edges, np.asarray(d, float), side="left")]
    if vc is not None:
        out = np.where(np.asarray(vc) > 1.0, "F", out)
    return out


def los_roundabout(d: np.ndarray, vc: np.ndarray | None = None) -> np.ndarray:
    edges = np.array([10, 15, 25, 35, 50])
    letters = np.array(list("ABCDEF"))
    out = letters[np.searchsorted(edges, np.asarray(d, float), side="left")]
    if vc is not None:
        out = np.where(np.asarray(vc) > 1.0, "F", out)
    return out
