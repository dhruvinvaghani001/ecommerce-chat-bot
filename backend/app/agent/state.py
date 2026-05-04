from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class SearchContext(TypedDict, total=False):
    query: str
    name: str
    price: str
    minPrice: Optional[float]
    maxPrice: Optional[float]
    page: int
    pageSize: int
    attributes: dict[str, Any]
    summary: str


class PendingSearchConfirmation(TypedDict, total=False):
    userRequest: str
    currentSearch: SearchContext
    proposedSearch: SearchContext


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    components: list[dict]
    thread_id: str
    last_search_context: Optional[SearchContext]
    pending_search_confirmation: Optional[PendingSearchConfirmation]
