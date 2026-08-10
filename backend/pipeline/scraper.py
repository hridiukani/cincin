import asyncio
import re

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

PAGE_TIMEOUT_MS = 15_000

# Words that flag happy-hour / specials content in link text or page body.
HH_KEYWORDS = re.compile(r"\b(happy\s*hour|specials|deals|drink specials|drinks|hh)\b", re.I)

# Words that flag a multi-location chooser (modal / dropdown / button).
LOCATION_KEYWORDS = re.compile(
    r"\b(select|choose|find|pick)\s+(a\s+)?location\b|\bfind\s+a\s+(store|restaurant)\b",
    re.I,
)

# Time ranges like "3pm-6pm", "3:00-6:00", "4:30 pm to 7 pm".
TIME_RANGE = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*(?:-|–|—|to)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b"
    r"|\b\d{1,2}:\d{2}\s*(?:-|–|—|to)\s*\d{1,2}:\d{2}\b",
    re.I,
)


def _is_pdf_href(href: str) -> bool:
    return href.split("?")[0].split("#")[0].lower().endswith(".pdf")


def detect_pattern(html: str, text: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)

    # 1/2. An anchor whose text mentions happy hour — route to the PDF parser
    #      if it points at a PDF, otherwise treat it as a page to follow.
    for a in anchors:
        if HH_KEYWORDS.search(a.get_text(" ", strip=True)):
            href = a["href"]
            if _is_pdf_href(href):
                return {"pattern": "pdf", "target": href}
            return {"pattern": "link", "target": href}

    # 2. Any standalone PDF link (e.g. a menu PDF) worth parsing.
    for a in anchors:
        if _is_pdf_href(a["href"]):
            return {"pattern": "pdf", "target": a["href"]}

    # 3. A location chooser that must be interacted with before content loads.
    if LOCATION_KEYWORDS.search(text):
        return {"pattern": "location_selector", "target": True}

    # 4. Happy-hour content sitting directly in the page text.
    if HH_KEYWORDS.search(text) and TIME_RANGE.search(text):
        return {"pattern": "inline", "target": None}

    return {"pattern": "none", "target": None}


async def load_page(url: str) -> dict | None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
            html = await page.content()
            text = await page.inner_text("body")
            print(f"[scraper] OK   {url}")
            return {"html": html, "text": text}
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            print(f"[scraper] FAIL {url} - {type(e).__name__}: {str(e).splitlines()[0]}")
            return None
        finally:
            await browser.close()


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    result = asyncio.run(load_page(target))
    if result:
        print(f"html: {len(result['html'])} chars, text: {len(result['text'])} chars")
