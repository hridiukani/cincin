import asyncio

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

PAGE_TIMEOUT_MS = 15_000


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
