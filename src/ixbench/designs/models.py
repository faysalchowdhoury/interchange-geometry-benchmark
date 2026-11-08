"""Conventional diamond, diverging diamond and turbo-roundabout dumbbell.

Every design analyses the WEST terminal; the east is its mirror image. Results are:

* ``max_vc``     worst node volume/capacity ratio (the screening criterion);
* ``delay``      average control delay per vehicle *entering the interchange*, so a through
                 vehicle stopping at two signals counts twice, as drivers experience it;
* ``nodes``      per-node v/c for diagnostics.

Routing (west terminal; "outer" = arterial approach from the west, "inner" = off the bridge)::

    outer_through = through + on_left       inner_through = through + off_left
    inner_left    = on_left (onto this on-ramp)   off-ramp: off_left (over the bridge), off_right

**Diamond** (3 critical phases: inner left, throughs, off-ramp; outer right turn free)::

    CLV = max(inner_left/n_L + outer_through/n_T, inner_through/n_T) + max(off_left/n_OL, off_right/n_OR)

**DDI** (crossover: 2 phases; on-ramp lefts free on the crossed-over side; off-ramp right free)::

    CLV_crossover = outer_through/n_T + inner_through/n_T
    CLV_offramp   = off_left/n_OL + outer_through/n_T   (off-ramp lefts merge into the eastbound
                                                       crossed-over stream)

**Turbo-roundabout dumbbell** (legs W arterial, E bridge, N off-ramp entry, S on-ramp exit;
counter-clockwise circulation). Circulating flow in front of each entry follows from the
routing above. In a turbo roundabout the raised lane dividers let the right entry lane yield only
to the *outer* circulating lane (flow exiting at the next leg), so it is analysed with the
single-lane HCM model against that flow; the left entry lane yields to all circulating flow (HCM
two-lane, left-lane model). This captures the turbo design principle but uses HCM, not
turbo-specific, coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from pydantic import Field

from ..core.capacity import (
    clv_vc,
    rbt_capacity_single,
    rbt_capacity_two_lane,
    rbt_delay,
    signal_delay,
)
from ..core.demand import Demand
from ..core.config import StrictModel


class LaneConfig(StrictModel):
    through: int = Field(2, ge=1, le=4)
    inner_left: int = Field(1, ge=1, le=3)
    off_left: int = Field(1, ge=1, le=3)
    off_right: int = Field(1, ge=1, le=2)


@dataclass
class DesignResult:
    name: str
    max_vc: np.ndarray
    delay: np.ndarray
    nodes: dict[str, np.ndarray] = field(default_factory=dict)


def diamond(d: Demand, lanes: LaneConfig) -> DesignResult:
    n = lanes
    il = d.on_left / n.inner_left
    ot = d.outer_through / n.through
    it = d.inner_through / n.through
    off_crit = np.maximum(d.off_left / n.off_left, d.off_right / n.off_right)
    art = np.maximum(il + ot, it)
    clv = art + off_crit
    phase_b = np.maximum(ot, it - il)
    delay_node, _ = signal_delay(
        [d.on_left, d.outer_through + d.inner_through, d.off_left + d.off_right],
        [il, np.maximum(phase_b, 0.0), off_crit],
    )
    node_flow = d.on_left + d.outer_through + d.inner_through + d.off_ramp
    delay = 2.0 * node_flow * delay_node / d.total_entering
    vc = clv_vc(clv)
    return DesignResult("diamond", vc, delay, {"terminal": vc})


def ddi(d: Demand, lanes: LaneConfig) -> DesignResult:
    n = lanes
    ot = d.outer_through / n.through
    it = d.inner_through / n.through
    ol = d.off_left / n.off_left
    clv_x = ot + it
    clv_off = ol + ot
    dx, _ = signal_delay([d.outer_through, d.inner_through], [ot, it])
    doff, _ = signal_delay([d.off_left, np.zeros_like(ot)], [ol, ot])  # through platoon assumed coordinated
    delay = 2.0 * ((d.outer_through + d.inner_through) * dx + d.off_left * doff) / d.total_entering
    vc_x, vc_off = clv_vc(clv_x), clv_vc(clv_off)
    return DesignResult("ddi", np.maximum(vc_x, vc_off), delay, {"crossover": vc_x, "offramp_merge": vc_off})


def turbo(d: Demand, lanes: LaneConfig) -> DesignResult:
    ot, it = d.outer_through, d.inner_through
    # entry W (arterial from the west): right lane = on-ramp rights + half the through
    w_right_v, w_left_v = d.on_right + 0.5 * ot, 0.5 * ot
    w_outer = d.on_left  # E->S exits at the next leg after W: outer lane
    w_total = d.on_left + d.off_left
    w_right_c = rbt_capacity_single(w_outer)
    _, w_left_c = rbt_capacity_two_lane(w_total)
    # entry E (off the bridge): nothing circulates past it (N is entry-only, S exit-only)
    e_right_c, e_left_c = rbt_capacity_two_lane(np.zeros_like(ot))
    e_right_v, e_left_v = 0.5 * it, d.on_left + 0.5 * it
    # entry N (off-ramp)
    n_outer = it  # E->W exits at the next leg after N
    n_total = it + d.on_left
    n_right_c = rbt_capacity_single(n_outer)
    _, n_left_c = rbt_capacity_two_lane(n_total)
    n_right_v, n_left_v = d.off_right, d.off_left
    lanes_v = [w_right_v, w_left_v, e_right_v, e_left_v, n_right_v, n_left_v]
    lanes_c = [w_right_c, w_left_c, e_right_c, e_left_c, n_right_c, n_left_c]
    x = [v / c for v, c in zip(lanes_v, lanes_c)]
    vc = np.max(np.stack(x), axis=0)
    flow = sum(lanes_v)
    dsum = sum(v * rbt_delay(v, c) for v, c in zip(lanes_v, lanes_c))
    delay = 2.0 * dsum / d.total_entering
    return DesignResult("turbo_roundabout", vc, delay,
                        {"entry_arterial": np.maximum(x[0], x[1]), "entry_bridge": np.maximum(x[2], x[3]),
                         "entry_offramp": np.maximum(x[4], x[5]), "flow": flow})


DESIGNS = {"diamond": diamond, "ddi": ddi, "turbo_roundabout": turbo}


def evaluate_all(d: Demand, lanes: LaneConfig | None = None) -> dict[str, DesignResult]:
    lanes = lanes or LaneConfig()
    return {name: fn(d, lanes) for name, fn in DESIGNS.items()}


def capacity_reserve(d: Demand, design: str, lanes: LaneConfig | None = None, *, target_vc: float = 1.0,
                     iterations: int = 40) -> np.ndarray:
    """Largest uniform demand multiplier keeping the worst node at ``target_vc`` (vectorised bisection)."""
    lanes = lanes or LaneConfig()
    fn = DESIGNS[design]
    shape = np.broadcast(d.through, d.off_ramp).shape
    lo = np.zeros(shape)
    hi = np.full(shape, 10.0)
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        ok = fn(d.scaled(mid), lanes).max_vc <= target_vc
        lo = np.where(ok, mid, lo)
        hi = np.where(ok, hi, mid)
    return lo
