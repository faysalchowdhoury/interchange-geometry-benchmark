from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ixbench.api.app import create_app
from ixbench.core.capacity import rbt_capacity_single, rbt_capacity_two_lane, rbt_delay, signal_delay
from ixbench.core.demand import Demand
from ixbench.designs.models import LaneConfig, capacity_reserve, ddi, diamond, evaluate_all, turbo
from ixbench.study import best_design, grid, monte_carlo

L = LaneConfig()


def test_routing_identities() -> None:
    d = Demand.of(1000, 600, off_left_share=0.5)
    assert d.outer_through == 1300 and d.inner_through == 1300 and d.on_left == 300
    assert d.total_entering == 2 * (1000 + 600) + 2 * 600
    with pytest.raises(ValueError):
        Demand.of(100, 100, off_left_share=1.5)


def test_diamond_clv_hand_calculation() -> None:
    d = Demand.of(1000, 600, off_left_share=0.5)
    # max(300/1 + 1300/2, 1300/2) + max(300, 300) = 950 + 300 = 1250 -> v/c 0.781
    assert float(diamond(d, L).max_vc) == pytest.approx(1250 / 1600)


def test_ddi_clv_hand_calculation() -> None:
    d = Demand.of(1000, 600, off_left_share=0.5)
    # crossover 650 + 650 = 1300; off-ramp merge 300 + 650 = 950 -> worst 1300/1600
    r = ddi(d, L)
    assert float(r.nodes["crossover"]) == pytest.approx(1300 / 1600)
    assert float(r.nodes["offramp_merge"]) == pytest.approx(950 / 1600)


def test_hcm_roundabout_formulas() -> None:
    assert float(rbt_capacity_single(0.0)) == pytest.approx(1380)
    assert float(rbt_capacity_single(1000.0)) == pytest.approx(1380 * np.exp(-1.02))
    r, l = rbt_capacity_two_lane(500.0)
    assert float(r) == pytest.approx(1420 * np.exp(-0.425)) and float(l) == pytest.approx(1350 * np.exp(-0.46))
    # low v/c delay ~ 3600/c + 5x
    assert float(rbt_delay(10.0, 1000.0)) == pytest.approx(3.6 + 0.05, abs=0.2)


def test_turbo_bridge_entry_is_unopposed() -> None:
    d = Demand.of(1000, 600, off_left_share=0.5)
    r = turbo(d, L)
    assert float(r.nodes["entry_bridge"]) < float(r.nodes["entry_offramp"])


def test_monotonic_and_vectorised() -> None:
    d = grid(np.array([500.0, 1000.0, 1500.0]), np.array([400.0, 800.0]), np.array([0.5]))
    res = evaluate_all(d)
    for r in res.values():
        assert r.max_vc.shape == (3, 2, 1)
        assert np.all(np.diff(r.max_vc[:, 0, 0]) > 0)  # more through traffic -> higher v/c
        assert np.all(r.delay > 0)
    assert best_design(res).shape == (3, 2, 1)


def test_capacity_reserve_hits_unity() -> None:
    d = Demand.of(1000, 600)
    for n in ("diamond", "ddi", "turbo_roundabout"):
        f = float(capacity_reserve(d, n))
        assert float(evaluate_all(d.scaled(f))[n].max_vc) == pytest.approx(1.0, abs=1e-6)


def test_signal_delay_increases_with_flow() -> None:
    low, _ = signal_delay([np.array(400.0), np.array(400.0)], [np.array(200.0), np.array(200.0)])
    high, _ = signal_delay([np.array(1400.0), np.array(1400.0)], [np.array(700.0), np.array(700.0)])
    assert float(high) > float(low) > 0


def test_monte_carlo_bounds() -> None:
    m = monte_carlo({"through": 1000.0, "off_ramp": 600.0, "off_left_share": 0.5}, samples=2000)
    assert all(0.0 <= m[n] <= 1.0 for n in ("diamond", "ddi", "turbo_roundabout"))
    assert 1.2 < m["median_factor"] < 1.5


def test_api() -> None:
    c = TestClient(create_app())
    r = c.post("/v1/screen", json={"through_vph": 1000, "off_ramp_vph": 600})
    assert r.status_code == 200 and len(r.json()) == 3
    assert c.post("/v1/screen", json={"through_vph": -1, "off_ramp_vph": 600}).status_code == 422
