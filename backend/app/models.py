from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


class ActionInstruction(BaseModel):
    type: str = Field(description="quick_reply | navigate")
    options: dict


class ProductAction(BaseModel):
    text: str
    icon: str
    instructions: list[ActionInstruction]


class ProductItem(BaseModel):
    item_id: str = Field(alias="itemId")
    slug: str
    title: str
    description: str = ""
    badge: str = ""
    highlight: str = ""
    images: list[str] = []
    url: str = ""
    actions: list[ProductAction] = []

    class Config:
        populate_by_name = True


class Pagination(BaseModel):
    page_no: int = Field(default=1, alias="pageNo")
    page_size: int = Field(default=20, alias="pageSize")
    total_pages: int = Field(default=1, alias="totalPages")
    total_items: int = Field(default=0, alias="totalItems")

    class Config:
        populate_by_name = True


class CardListComponent(BaseModel):
    type: str = "card-list"
    data: dict


class CardDetailComponent(BaseModel):
    type: str = "card-detail"
    data: dict


class ChatRequest(BaseModel):
    content: str
    thread_id: Optional[str] = None


class ChatResponseMessage(BaseModel):
    type: str = "assistant"
    content: str = ""
    components: list[dict] = []
    thread_id: str = ""
