import asyncio
import re
from urllib.parse import urljoin

import fitz
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser
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


async def handle_link(browser: Browser, url: str) -> str | None:
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
        text = await page.inner_text("body")
        print(f"[handle_link] OK   {url}")
        return text
    except (PlaywrightTimeoutError, PlaywrightError) as e:
        print(f"[handle_link] FAIL {url} - {type(e).__name__}: {str(e).splitlines()[0]}")
        return None
    finally:
        await page.close()


async def handle_pdf(pdf_url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()
        doc = fitz.open(stream=response.content, filetype="pdf")
    except httpx.HTTPError as e:
        print(f"[handle_pdf] FAIL {pdf_url} - download error: {e}")
        return None
    except Exception as e:  # fitz raises on corrupted / non-PDF data
        print(f"[handle_pdf] FAIL {pdf_url} - could not open PDF: {type(e).__name__}: {e}")
        return None

    try:
        if doc.needs_pass:
            print(f"[handle_pdf] FAIL {pdf_url} - password protected")
            return None
        text = "\n".join(page.get_text() for page in doc)
        print(f"[handle_pdf] OK   {pdf_url}")
        return text
    except Exception as e:
        print(f"[handle_pdf] FAIL {pdf_url} - extraction error: {type(e).__name__}: {e}")
        return None
    finally:
        doc.close()


async def handle_location_selector(browser: Browser, base_url: str) -> str | None:
    page = await browser.new_page()
    try:
        await page.goto(base_url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)

        option = page.locator(
            "a[href*='location' i], button:has-text('location'), "
            "[class*='location' i] a, select option:nth-child(2)"
        ).first
        if await option.count() == 0:
            print(f"[handle_location_selector] no location option found at {base_url}")
            return await page.inner_text("body")

        await option.click()
        await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)

        html = await page.content()
        text = await page.inner_text("body")

        # After selecting a location the real content is loaded, so re-detect:
        # the happy-hour info may now sit behind a fresh link to follow.
        detected = detect_pattern(html, text)
        if detected["pattern"] == "link" and detected["target"]:
            followed = await handle_link(browser, urljoin(page.url, detected["target"]))
            if followed is not None:
                return followed

        print(f"[handle_location_selector] OK   {base_url}")
        return text
    except (PlaywrightTimeoutError, PlaywrightError) as e:
        print(f"[handle_location_selector] FAIL {base_url} - {type(e).__name__}: {str(e).splitlines()[0]}")
        return None
    finally:
        await page.close()


async def scrape_venue(venue: dict) -> dict:
    url = venue.get("website")
    if not url:
        return {"text": "", "pattern": "none", "success": False}

    page_data = await load_page(url)
    if page_data is None:
        return {"text": "", "pattern": "none", "success": False}

    detected = detect_pattern(page_data["html"], page_data["text"])
    pattern = detected["pattern"]
    target = detected["target"]

    if pattern in ("inline", "none"):
        text = page_data["text"]
        return {"text": text, "pattern": pattern, "success": bool(text)}

    if pattern == "pdf":
        text = await handle_pdf(urljoin(url, target))
        return {"text": text or "", "pattern": pattern, "success": text is not None}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            if pattern == "link":
                text = await handle_link(browser, urljoin(url, target))
            else:  # location_selector
                text = await handle_location_selector(browser, url)
        finally:
            await browser.close()

    return {"text": text or "", "pattern": pattern, "success": bool(text)}


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    result = asyncio.run(scrape_venue({"id": None, "name": "cli-test", "website": target}))
    print(f"pattern={result['pattern']} success={result['success']} text={len(result['text'])} chars")
