from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.gateway.schemas.v1.common import RunDTO


class RunCancelRequest(BaseModel):
    action: Literal["interrupt", "rollback"] = "interrupt"
    wait: bool = False


class RunCancelResponse(BaseModel):
    run_id: str
    status: str


class RunResponse(RunDTO):
    pass
