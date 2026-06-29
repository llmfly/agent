from __future__ import annotations

from pydantic import BaseModel


class CapabilitiesResponse(BaseModel):
    conversation: dict[str, bool]
    agents: dict[str, bool]
    data_sources: dict[str, bool]
    reports: dict[str, bool]
    logo: dict[str, bool]
