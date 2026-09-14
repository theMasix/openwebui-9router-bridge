"""Pydantic schemas for inbound and outbound search payloads."""

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------
# OpenWebUI External Search Schemas (Inbound)
# ---------------------------------------------------------

class OpenWebUISearchRequest(BaseModel):
    """Payload received from OpenWebUI external search."""

    query: str = Field(..., min_length=1, description="Search query string")
    count: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Suggested maximum number of search results",
    )


class OpenWebUISearchResult(BaseModel):
    """Single search result expected by OpenWebUI."""

    link: str = Field(default="", description="Direct URL of the search result")
    title: str = Field(default="", description="Title of the search result page")
    snippet: str = Field(
        default="",
        description="Descriptive text snippet from the page content",
    )


# ---------------------------------------------------------
# 9Router Search Schemas (Outbound)
# ---------------------------------------------------------

class NineRouterSearchRequest(BaseModel):
    """Payload sent to 9Router POST /v1/search."""

    model: str = Field(..., description="Provider or combo model name")
    query: str = Field(..., description="Search query string")
    max_results: int = Field(
        default=5,
        ge=1,
        description="Maximum search results",
    )


class NineRouterResultItem(BaseModel):
    """Result item returned by 9Router."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default="")
    url: str | None = Field(default="")
    snippet: str | None = Field(default="")
    display_url: str | None = Field(default=None)
    score: float | None = Field(default=None)
    position: int | None = Field(default=None)


class NineRouterSearchResponse(BaseModel):
    """Response payload returned by 9Router."""

    model_config = ConfigDict(extra="ignore")

    provider: str | None = Field(default=None)
    query: str | None = Field(default=None)
    results: list[NineRouterResultItem] = Field(default_factory=list)


def map_ninerouter_to_openwebui(
    response: NineRouterSearchResponse,
) -> list[OpenWebUISearchResult]:
    """Transform 9Router response items to OpenWebUI format."""
    transformed: list[OpenWebUISearchResult] = []
    for item in response.results:
        link = item.url or item.display_url or ""
        transformed.append(
            OpenWebUISearchResult(
                link=link,
                title=item.title or "",
                snippet=item.snippet or "",
            )
        )
    return transformed
