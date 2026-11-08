"""``ixbench`` command line: ``study`` (sweep + report), ``screen`` (one demand set), ``serve``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ixbench")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("study")
    s.add_argument("--out", default="results/screening")
    s = sub.add_parser("screen")
    s.add_argument("--through", type=float, required=True)
    s.add_argument("--off-ramp", type=float, required=True)
    s.add_argument("--left-share", type=float, default=0.5)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    if a.cmd == "study":
        from .report import write_report
        from .study import run

        summary = run(a.out)
        print(write_report(summary, Path(a.out)).read_text(encoding="utf-8"))
    elif a.cmd == "screen":
        from fastapi.testclient import TestClient

        from .api.app import create_app

        r = TestClient(create_app()).post("/v1/screen", json={"through_vph": a.through, "off_ramp_vph": a.off_ramp,
                                                               "off_left_share": a.left_share})
        print(json.dumps(r.json(), indent=2))
    else:
        import uvicorn

        from .api.app import create_app

        uvicorn.run(create_app(), host="127.0.0.1", port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
