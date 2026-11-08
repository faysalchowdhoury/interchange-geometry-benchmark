"""Batch screening: demand-grid sweep, capacity reserve, Monte Carlo design-year risk, benchmark."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .core.capacity import los_roundabout, los_signalized
from .core.demand import Demand
from .designs.models import DESIGNS, LaneConfig, capacity_reserve, evaluate_all

NAMES = list(DESIGNS)
LABEL = {"diamond": "Conventional diamond", "ddi": "Diverging diamond (DDI)", "turbo_roundabout": "Turbo-roundabout dumbbell"}
REFERENCE = {
    "balanced": dict(through=1000.0, off_ramp=600.0, off_left_share=0.5),
    "heavy_left": dict(through=900.0, off_ramp=900.0, off_left_share=0.7),
    "arterial_dominant": dict(through=1500.0, off_ramp=400.0, off_left_share=0.4),
}


def grid(through: np.ndarray, ramps: np.ndarray, shares: np.ndarray) -> Demand:
    a, r, s = np.meshgrid(through, ramps, shares, indexing="ij")
    return Demand.of(a, r, off_left_share=s)


def best_design(results: dict, vc_limit: float = 1.0) -> np.ndarray:
    """Index of the lowest-delay design among those with v/c <= limit (lowest v/c if none qualifies)."""
    vc = np.stack([results[n].max_vc for n in NAMES])
    dl = np.stack([results[n].delay for n in NAMES])
    feasible = vc <= vc_limit
    score = np.where(feasible, dl, 1e9 + vc)
    return np.argmin(score, axis=0)


def monte_carlo(base: dict[str, float], *, years: int = 20, samples: int = 20_000, seed: int = 0,
                lanes: LaneConfig | None = None) -> dict[str, float]:
    """P(worst node v/c > 1 in the design year) under uncertain base demand and growth."""
    rng = np.random.default_rng(seed)
    base_err = rng.lognormal(0.0, 0.10, samples)  # +/-10% base-year count uncertainty
    growth = rng.normal(0.015, 0.0075, samples)  # 1.5 %/yr +/- 0.75
    factor = base_err * (1.0 + growth) ** years
    d = Demand.of(base["through"], base["off_ramp"], off_left_share=base["off_left_share"]).scaled(factor)
    res = evaluate_all(d, lanes)
    return {n: float((res[n].max_vc > 1.0).mean()) for n in NAMES} | {"median_factor": float(np.median(factor))}


def run(out_dir: str | Path, lanes: LaneConfig | None = None) -> dict[str, Any]:
    lanes = lanes or LaneConfig()
    out = Path(out_dir)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    through = np.arange(300, 1801, 50, dtype=float)
    ramps = np.arange(200, 1401, 50, dtype=float)
    shares = np.array([0.3, 0.5, 0.7])
    d = grid(through, ramps, shares)
    t0 = time.perf_counter()
    res = evaluate_all(d, lanes)
    sweep_s = time.perf_counter() - t0
    best = best_design(res)
    rows = []
    for idx in np.ndindex(best.shape):
        row = {"through": through[idx[0]], "off_ramp": ramps[idx[1]], "left_share": shares[idx[2]],
               "best": NAMES[best[idx]]}
        for n in NAMES:
            row[f"{n}_vc"] = float(res[n].max_vc[idx])
            row[f"{n}_delay"] = float(res[n].delay[idx])
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(out / "sweep.csv", index=False)
    share_best = table.groupby("left_share")["best"].value_counts(normalize=True).unstack(fill_value=0.0)
    feasible = {n: float((table[f"{n}_vc"] <= 1.0).mean()) for n in NAMES}

    ref_rows = []
    for key, base in REFERENCE.items():
        dd = Demand.of(base["through"], base["off_ramp"], off_left_share=base["off_left_share"])
        r = evaluate_all(dd, lanes)
        for n in NAMES:
            vc, dl = float(r[n].max_vc), float(r[n].delay)
            los = (los_roundabout if n == "turbo_roundabout" else los_signalized)(np.array(dl), np.array(vc))
            ref_rows.append({"case": key, "design": n, "max_vc": vc, "delay_s": dl, "los": str(los),
                             "capacity_reserve": float(capacity_reserve(dd, n, lanes)),
                             "nodes": {k: float(v) for k, v in r[n].nodes.items() if k != "flow"}})
    mc = {k: monte_carlo(b, lanes=lanes) for k, b in REFERENCE.items()}

    # throughput benchmark: one million demand scenarios through all three designs
    big = Demand.of(np.random.default_rng(1).uniform(300, 1800, 1_000_000), np.random.default_rng(2).uniform(200, 1400, 1_000_000),
                    off_left_share=np.random.default_rng(3).uniform(0.2, 0.8, 1_000_000))
    t0 = time.perf_counter()
    evaluate_all(big, lanes)
    bench_s = time.perf_counter() - t0

    summary = {"lanes": lanes.model_dump(), "grid_scenarios": int(best.size), "sweep_seconds": sweep_s,
               "share_best_by_left_share": share_best.round(3).to_dict(orient="index"),
               "feasible_share": feasible, "reference": ref_rows, "monte_carlo_2045": mc,
               "benchmark": {"scenarios": 1_000_000, "designs": 3, "seconds": bench_s,
                             "evaluations_per_s": 3_000_000 / bench_s}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    _plots(through, ramps, shares, res, best, out / "figures")
    return summary


def _plots(through, ramps, shares, res, best, fig_dir: Path) -> None:  # type: ignore[no-untyped-def]
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    cmap = ListedColormap(["#868e96", "#1c7ed6", "#2b8a3e"])
    fig, axes = plt.subplots(1, len(shares), figsize=(5 * len(shares), 4.3), sharey=True)
    for k, ax in enumerate(np.atleast_1d(axes)):
        b = best[:, :, k].T
        ax.pcolormesh(through, ramps, b, cmap=cmap, vmin=-0.5, vmax=2.5, shading="nearest")
        for n, style in (("diamond", ":"), ("ddi", "--"), ("turbo_roundabout", "-")):
            ax.contour(through, ramps, res[n].max_vc[:, :, k].T, levels=[1.0], colors="k", linestyles=style, linewidths=1)
        ax.set_title(f"off-ramp left share {shares[k]:.0%}", fontsize=10)
        ax.set_xlabel("arterial through volume per direction (veh/h)")
    np.atleast_1d(axes)[0].set_ylabel("volume per ramp (veh/h)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in ("#868e96", "#1c7ed6", "#2b8a3e")]
    handles += [plt.Line2D([], [], color="k", ls=s) for s in (":", "--", "-")]
    labels = [f"best: {LABEL[n]}" for n in NAMES] + [f"v/c = 1: {LABEL[n]}" for n in NAMES]
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    fig.savefig(fig_dir / "best_design_map.png", dpi=130)
    plt.close(fig)
