from typing import TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ApiResponse[DataT](BaseModel):
    success: bool = True
    data: DataT | None = None
    message: str = "操作成功"
