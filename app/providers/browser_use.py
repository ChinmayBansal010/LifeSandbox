"""Optional public-web research through a local Browser Use Chromium session."""

import asyncio
import importlib.util
import json
import os
import re
import tempfile
from urllib.parse import quote_plus

from app.core.config import get_settings

GITHUB_RESERVED_PATHS = {
    "about",
    "apps",
    "collections",
    "contact",
    "enterprise",
    "features",
    "login",
    "marketplace",
    "orgs",
    "organizations",
    "pricing",
    "security",
    "site",
    "sponsors",
    "topics",
}


def is_configured() -> bool:
    settings = get_settings()
    if not settings.browser_use_enabled or importlib.util.find_spec("browser_use") is None:
        return False
    if settings.llm_provider == "openrouter":
        return bool(settings.openrouter_api_key and settings.openrouter_model)
    if settings.llm_provider == "nebius":
        return bool(settings.nebius_api_key and settings.nebius_model)
    return False


def is_repository_url(url: str) -> bool:
    match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)/?", url.rstrip("/"))
    return bool(match and match.group(1).lower() not in GITHUB_RESERVED_PATHS)


def has_no_repository_results(text: str) -> bool:
    return "your search did not match any repositories" in text.lower()


def _github_search_terms(query: str) -> list[str]:
    text = re.sub(r"\s+", " ", query.strip())
    first_sentence = text.split(".", 1)[0][:180]
    normalized = first_sentence.lower()
    searches = [first_sentence]
    if "zcu104" in normalized and any(word in normalized for word in ("fpga", "accelerator", "ai")):
        searches.append("ZCU104 FPGA AI accelerator")
    if any(word in normalized for word in ("fpga", "accelerator", "ai")):
        searches.append("FPGA AI accelerator")
    return list(dict.fromkeys(term for term in searches if term))[:3]


async def research_with_browser(query: str) -> dict[str, str]:
    if not 1 <= len(query.strip()) <= 1000:
        raise ValueError("Browser research query must be between 1 and 1000 characters")
    if not is_configured():
        raise RuntimeError("Browser Use is disabled or not configured")

    os.environ.setdefault(
        "BROWSER_USE_CONFIG_DIR",
        os.path.join(tempfile.gettempdir(), "life-sandbox-browser-use"),
    )
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
    os.environ.setdefault("BROWSER_USE_CLOUD_SYNC", "false")
    os.environ.setdefault("BROWSER_USE_DISABLE_EXTENSIONS", "1")

    from browser_use import Browser

    with tempfile.TemporaryDirectory(prefix="life-sandbox-browser-") as profile_dir:
        browser = Browser(
            headless=True,
            user_data_dir=profile_dir,
            enable_default_extensions=False,
            accept_downloads=False,
            allowed_domains=["github.com"],
        )
        try:
            await browser.start()
            page = await browser.new_page()
            search_results: list[dict[str, str]] = []
            search_url = ""
            for terms in _github_search_terms(query):
                search_url = (
                    "https://github.com/search?q=" + quote_plus(terms) + "&type=repositories"
                )
                await page.goto(search_url)
                await asyncio.sleep(1.5)
                raw = await page.evaluate(
                    r"""() => JSON.stringify({
                        title: document.title,
                        text: (document.body?.innerText || '').slice(0, 5000),
                        links: Array.from(document.querySelectorAll('a[href]'))
                            .map(a => ({href: a.href, text: (a.innerText || '').trim()}))
                            .filter(a => /^https:\/\/github\\.com\/[^/]+\/[^/]+\/?$/.test(a.href))
                    })"""
                )
                page_data = json.loads(raw or "{}")
                search_text = page_data.get("text", "")
                if has_no_repository_results(search_text):
                    continue
                for link in page_data.get("links", []):
                    url = link.get("href", "").rstrip("/")
                    if is_repository_url(url):
                        path = url.removeprefix("https://github.com/")
                        search_results.append(
                            {"url": url, "name": link.get("text", "").strip() or path}
                        )
                if len({item["url"] for item in search_results}) >= 3:
                    break

            unique_results = []
            seen = set()
            for item in search_results:
                if item["url"] not in seen:
                    seen.add(item["url"])
                    unique_results.append(item)
            if not unique_results:
                raise RuntimeError(f"GitHub search returned no repository links: {search_url}")

            evidence = [
                f"GitHub search page: {search_url}\n{search_text[:2500]}",
                "Repository pages inspected below were opened directly in the local browser.",
            ]
            for repository in unique_results[:3]:
                await page.goto(repository["url"])
                await asyncio.sleep(1.0)
                details = await page.evaluate(
                    """() => JSON.stringify({
                        title: document.title,
                        url: location.href,
                        text: (document.body?.innerText || '').slice(0, 5000)
                    })"""
                )
                page_data = json.loads(details or "{}")
                evidence.append(
                    f"Repository: {page_data.get('url') or repository['url']}\n"
                    f"Title: {page_data.get('title', '')}\n"
                    f"Page text:\n{page_data.get('text', '')}"
                )
            return {"result": "\n\n---\n\n".join(evidence)[:18000]}
        finally:
            await browser.kill()
