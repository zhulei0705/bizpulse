from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str | None = None


class PageData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    message: str


def clamp_page_size(value: int, maximum: int = 100) -> int:
    return max(1, min(value, maximum))
