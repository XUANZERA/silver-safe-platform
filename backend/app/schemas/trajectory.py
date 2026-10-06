from enum import StrEnum

from pydantic import BaseModel


class TrajectoryAttentionStatus(StrEnum):
    NORMAL = "NORMAL"
    ATTENTION = "ATTENTION"
    UNKNOWN = "UNKNOWN"


class TrajectoryAttentionResponse(BaseModel):
    status: TrajectoryAttentionStatus
    score: float | None
    reason_codes: list[str]
    model_version: str | None
    point_count: int
