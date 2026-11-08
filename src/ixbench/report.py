"""Markdown report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .study import LABEL, NAMES


def write_report(s: dict[str, Any], out: Path) -> Path:
    L = ["# Interchange screening results", "",
         f"Lanes: {s['lanes']}. {s['grid_scenarios']:,} grid scenarios evaluated in {s['sweep_seconds'] * 1000:.0f} ms.", "",
         "## Reference demand cases", "",
         "| Case | Design | Worst node v/c | Delay per entering veh | LOS | Capacity reserve (x demand at v/c = 1) |",
         "|---|---|---|---|---|---|"]
    for r in s["reference"]:
        L.append(f"| {r['case']} | {LABEL[r['design']]} | {r['max_vc']:.2f} | {r['delay_s']:.1f} s | {r['los']} | {r['capacity_reserve']:.2f} |")
    L += ["", "## Share of the demand grid where each design is best (lowest delay with v/c <= 1)", "",
          "| Off-ramp left share | " + " | ".join(LABEL[n] for n in NAMES) + " |", "|" + "---|" * (len(NAMES) + 1)]
    for share, row in s["share_best_by_left_share"].items():
        L.append(f"| {float(share):.0%} | " + " | ".join(f"{100 * row.get(n, 0.0):.0f}%" for n in NAMES) + " |")
    L += ["", "Share of grid with worst node v/c <= 1: " + ", ".join(f"{LABEL[n]} {100 * v:.0f}%" for n, v in s["feasible_share"].items()), "",
          "## Monte Carlo: P(v/c > 1) in 2045", "",
          "Base-year counts +/-10% (lognormal), growth N(1.5%, 0.75%)/yr for 20 years, 20,000 draws.", "",
          "| Case | Median demand factor | " + " | ".join(LABEL[n] for n in NAMES) + " |", "|" + "---|" * (len(NAMES) + 2)]
    for case, m in s["monte_carlo_2045"].items():
        L.append(f"| {case} | {m['median_factor']:.2f} | " + " | ".join(f"{100 * m[n]:.0f}%" for n in NAMES) + " |")
    b = s["benchmark"]
    L += ["", f"Benchmark: {b['scenarios']:,} scenarios x {b['designs']} designs in {b['seconds']:.2f} s "
          f"({b['evaluations_per_s'] / 1e6:.1f} M design evaluations/s).", "", "![Best design](figures/best_design_map.png)", ""]
    md = out / "RESULTS.md"
    md.write_text("\n".join(L), encoding="utf-8")
    return md
