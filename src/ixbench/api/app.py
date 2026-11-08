"""``POST /v1/screen``: rank the three interchange forms for one demand set (vectorised core, < 1 ms)."""

from __future__ import annotations

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .. import __version__
from ..core.capacity import los_roundabout, los_signalized
from ..core.demand import Demand
from ..designs.models import DESIGNS, LaneConfig, capacity_reserve, evaluate_all


class ScreenRequest(BaseModel):
    through_vph: float = Field(ge=0, le=5000)
    off_ramp_vph: float = Field(ge=0, le=4000)
    on_ramp_vph: float | None = Field(None, ge=0, le=4000)
    off_left_share: float = Field(0.5, ge=0, le=1)
    on_left_share: float | None = Field(None, ge=0, le=1)
    lanes: LaneConfig = Field(default_factory=LaneConfig)


class DesignOut(BaseModel):
    design: str
    max_vc: float
    delay_s: float
    los: str
    capacity_reserve: float


def create_app() -> FastAPI:
    app = FastAPI(title="Interchange screening", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/screen", response_model=list[DesignOut])
    def screen(req: ScreenRequest) -> list[DesignOut]:
        d = Demand.of(req.through_vph, req.off_ramp_vph, req.on_ramp_vph, req.off_left_share, req.on_left_share)
        res = evaluate_all(d, req.lanes)
        out = []
        for n in DESIGNS:
            vc, dl = float(res[n].max_vc), float(res[n].delay)
            los = (los_roundabout if n == "turbo_roundabout" else los_signalized)(np.array(dl), np.array(vc))
            out.append(DesignOut(design=n, max_vc=round(vc, 3), delay_s=round(dl, 1), los=str(los),
                                 capacity_reserve=round(float(capacity_reserve(d, n, req.lanes)), 3)))
        return sorted(out, key=lambda o: (o.max_vc > 1.0, o.delay_s))

    return app
