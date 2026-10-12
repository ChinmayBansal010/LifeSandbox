from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, HttpUrl

from app.core.config import get_settings


class ResearchSource(BaseModel):
    title: str
    url: HttpUrl
    excerpt: str
    retrieved_at: datetime
    publisher: str | None = None


class ResearchUnavailable(RuntimeError):
    pass


async def research(query: str) -> list[ResearchSource]:
    settings = get_settings()
    if settings.research_provider != "tavily" or not settings.tavily_api_key:
        raise ResearchUnavailable(
            "Research is disabled; configure RESEARCH_PROVIDER=tavily and TAVILY_API_KEY"
        )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": 5,
                    "include_answer": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return [
                ResearchSource(
                    title=item.get("title") or item["url"],
                    url=item["url"],
                    excerpt=(item.get("content") or "")[:1200],
                    retrieved_at=datetime.now(UTC),
                    publisher=item.get("url", "").split("/")[2],
                )
                for item in payload.get("results", [])
            ]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise ResearchUnavailable("Research provider request failed") from exc
