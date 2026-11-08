"""Symmetric service-interchange demand, as origin-destination flows (veh/h).

Arterial runs east-west across a north-south freeway. Each ramp terminal (west, east) has an
off-ramp entering and an on-ramp leaving. The interchange is analysed with symmetric demand
(the west terminal mirrors the east), which is the usual screening assumption.

=================  ==========================================================
``through``        arterial through volume per direction (crosses both terminals)
``off_ramp``       volume per off-ramp
``on_ramp``        volume per on-ramp
``off_left_share`` share of each off-ramp turning left (across the bridge)
``on_left_share``  share of each on-ramp arriving as a left turn (from across the bridge)
=================  ==========================================================

All quantities broadcast, so one ``Demand`` can hold a whole scenario grid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Demand:
    through: np.ndarray
    off_ramp: np.ndarray
    on_ramp: np.ndarray
    off_left_share: np.ndarray
    on_left_share: np.ndarray

    @classmethod
    def of(cls, through: float | np.ndarray, off_ramp: float | np.ndarray, on_ramp: float | np.ndarray | None = None,
           off_left_share: float | np.ndarray = 0.5, on_left_share: float | np.ndarray | None = None) -> "Demand":
        on_ramp = off_ramp if on_ramp is None else on_ramp
        on_left_share = off_left_share if on_left_share is None else on_left_share
        arrs = np.broadcast_arrays(*(np.asarray(x, dtype=float) for x in (through, off_ramp, on_ramp, off_left_share, on_left_share)))
        if any((a < 0).any() for a in arrs) or (arrs[3] > 1).any() or (arrs[4] > 1).any():
            raise ValueError("volumes must be >= 0 and shares in [0, 1]")
        return cls(*arrs)

    def scaled(self, factor: float | np.ndarray) -> "Demand":
        f = np.asarray(factor, float)
        return Demand(self.through * f, self.off_ramp * f, self.on_ramp * f, self.off_left_share, self.on_left_share)

    # ---- movement flows at the WEST terminal (east is the mirror image)
    @property
    def off_left(self) -> np.ndarray:
        return self.off_ramp * self.off_left_share

    @property
    def off_right(self) -> np.ndarray:
        return self.off_ramp * (1.0 - self.off_left_share)

    @property
    def on_left(self) -> np.ndarray:
        """Vehicles from the far side of the bridge turning left onto this terminal's on-ramp."""
        return self.on_ramp * self.on_left_share

    @property
    def on_right(self) -> np.ndarray:
        return self.on_ramp * (1.0 - self.on_left_share)

    @property
    def outer_through(self) -> np.ndarray:
        """Arterial traffic approaching the terminal from outside, continuing over the bridge."""
        return self.through + self.on_left  # includes traffic bound for the far terminal's left-turn on-ramp

    @property
    def inner_through(self) -> np.ndarray:
        """Traffic coming off the bridge, continuing outward (arterial through + far off-ramp lefts)."""
        return self.through + self.off_left

    @property
    def total_entering(self) -> np.ndarray:
        """Vehicles entering the interchange per hour (both directions, both ramps)."""
        return 2.0 * (self.through + self.on_left + self.on_right) + 2.0 * self.off_ramp
