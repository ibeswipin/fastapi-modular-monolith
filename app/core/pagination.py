import math
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams:
    """Query params for any list endpoint: ?page=1&page_size=50."""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool

    @classmethod
    def build(cls, items: list[T], total: int, params: PaginationParams) -> "Page[T]":
        total_pages = math.ceil(total / params.page_size)
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
            has_next_page=params.page < total_pages,
            has_previous_page=params.page > 1,
        )
