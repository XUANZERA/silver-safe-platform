from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    elder_id: int | None = Field(default=None, ge=1)
    elder_name: str | None = Field(default=None, min_length=1, max_length=40)


class AIChatResponse(BaseModel):
    reply: str
    model: str
