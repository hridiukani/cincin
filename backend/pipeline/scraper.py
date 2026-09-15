import asyncio
import os
import re
from urllib.parse import urljoin

import fitz
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from playwright.async_api import Browser
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.6-flash"

PAGE_TIMEOUT_MS = 15_000
# Best-effort extra wait for JS-rendered content once the DOM is ready. Many
# bar/restaurant sites never reach full "networkidle" (chat widgets, ad and
# analytics beacons, live sockets), so we cap this and proceed regardless.
NETWORKIDLE_SETTLE_MS = 5_000


async def _settle(page) -> None:
    # Give client-rendered content a chance to appear, but never fail the load
    # just because the network never goes fully idle.
    try:
        await page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_SETTLE_MS)
    except PlaywrightTimeoutError:
        pass


async def _goto(page, url: str):
    response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    await _settle(page)
    return response


# Phrases used by "are you 21?" style age-verification gates that many
# bar/restaurant sites show before any real content.
AGE_GATE_KEYWORDS = [
    "are you 21",
    "i am 21",
    "yes, i'm 21",
    "enter your birthday",
    "verify your age",
    "i am of legal drinking age",
]

def _has_text_selector(tag: str, keyword: str) -> str:
    # Playwright's :has-text() needs its argument quoted; switch to double
    # quotes for any keyword (e.g. "i'm 21") that itself contains an apostrophe.
    if "'" in keyword:
        return f'{tag}:has-text("{keyword}")'
    return f"{tag}:has-text('{keyword}')"


_AGE_GATE_BUTTON_SELECTOR = ", ".join(
    _has_text_selector(tag, kw)
    for tag in ("button", "a")
    for kw in ("yes", "i am 21", "i'm 21", "enter")
)

_AGE_GATE_YEAR_INPUT_SELECTOR = (
    "input[name*='year' i], input[id*='year' i], input[placeholder*='year' i], "
    "input[name*='birth' i], input[id*='birth' i]"
)

_AGE_GATE_SUBMIT_SELECTOR = (
    "button[type='submit'], button:has-text('enter'), button:has-text('submit'), button:has-text('confirm')"
)


async def _bypass_age_gate(page, label: str) -> None:
    try:
        body_text = (await page.inner_text("body")).lower()
    except PlaywrightError:
        return

    if not any(keyword in body_text for keyword in AGE_GATE_KEYWORDS):
        return

    # Try a "Yes" / "I am 21" / "Enter" button first.
    button = page.locator(_AGE_GATE_BUTTON_SELECTOR).first
    if await button.count() > 0:
        try:
            await button.click(timeout=3000)
            await page.wait_for_timeout(2000)
            print(f"{label} [age gate bypassed] {page.url}")
            return
        except PlaywrightError:
            pass

    # No clickable button: fall back to filling a birth year field and submitting.
    year_input = page.locator(_AGE_GATE_YEAR_INPUT_SELECTOR).first
    if await year_input.count() > 0:
        try:
            await year_input.fill("1995")
            submit = page.locator(_AGE_GATE_SUBMIT_SELECTOR).first
            if await submit.count() > 0:
                await submit.click(timeout=3000)
            else:
                await year_input.press("Enter")
            await page.wait_for_timeout(2000)
            print(f"{label} [age gate bypassed] {page.url}")
        except PlaywrightError:
            pass


# Keywords used to locate the deal-relevant part of a page's body text.
_WINDOW_KEYWORDS = [
    "happy hour", "happy-hour", "hh", "specials", "lunch special",
    "late night", "deals", "drink special", "weekday",
]
_WINDOW_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _WINDOW_KEYWORDS) + r")\b", re.I
)
WINDOW_BEFORE = 1_000
WINDOW_AFTER = 2_000
WINDOW_FALLBACK_CHARS = 3_000


def _relevant_window(text: str) -> str:
    match = _WINDOW_KEYWORD_RE.search(text)
    if match is None:
        # No deal keyword anywhere: menus/deals tend to sit lower on the page
        # than navigation and hero content, so prefer the tail over the head.
        return text[-WINDOW_FALLBACK_CHARS:]
    idx = match.start()
    return text[max(0, idx - WINDOW_BEFORE) : idx + WINDOW_AFTER]


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


# A PDF is only worth parsing if its link text or URL hints at drinks/food/deals.
# This filters out privacy policies, allergen charts, accessibility docs, etc.
PDF_KEYWORDS = ("menu", "drink", "cocktail", "beer", "wine", "special", "happy", "hh", "food")


def _pdf_is_relevant(link_text: str, href: str) -> bool:
    haystack = f"{link_text} {href}".lower()
    return any(keyword in haystack for keyword in PDF_KEYWORDS)


# An <img> is only worth sending to Gemini if its src/alt/surrounding-anchor
# text hints it's a menu or deal image (not a logo, hero photo, food photo, etc).
IMAGE_MENU_KEYWORDS = ("menu", "happy", "special", "deal", "hour", "hh")

# Link-shortener domains commonly used for QR codes on printed table cards,
# which often point straight at a photographed menu image (or a webpage
# hosting one).
QR_SHORTLINK_DOMAINS = ("qrco.de", "qr.io", "bit.ly", "shorturl.at", "tinyurl.com", "rb.gy")

# Words in a shortlink's own anchor text ("View Menu", "Happy Hour Specials")
# that suggest it's worth following — separate from IMAGE_MENU_KEYWORDS since
# a shortlink gives no src/alt to inspect, only its link text.
SHORTLINK_MENU_KEYWORDS = ("menu", "happy", "special", "food", "drink", "view")


def _mentions_image_menu(*texts: str) -> bool:
    haystack = " ".join(t or "" for t in texts).lower()
    return any(keyword in haystack for keyword in IMAGE_MENU_KEYWORDS)


def _is_qr_shortlink(href: str) -> bool:
    return any(domain in href.lower() for domain in QR_SHORTLINK_DOMAINS)


def _shortlink_mentions_menu(link_text: str) -> bool:
    haystack = link_text.lower()
    return any(keyword in haystack for keyword in SHORTLINK_MENU_KEYWORDS)


def detect_pattern(html: str, text: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)

    # 1/2. An anchor whose text mentions happy hour — route to the PDF parser
    #      if it points at a PDF, otherwise treat it as a page to follow.
    #      QR shortlinks are excluded here: they're opaque redirects, not
    #      real content pages, so they fall through to step 6 below instead
    #      of being followed as a normal "link".
    for a in anchors:
        href = a["href"]
        if _is_qr_shortlink(href):
            continue
        if HH_KEYWORDS.search(a.get_text(" ", strip=True)):
            if _is_pdf_href(href):
                return {"pattern": "pdf", "target": href}
            return {"pattern": "link", "target": href}

    # 3. A standalone PDF link, but only if it looks drink/food/deal-related.
    #    An unrelated PDF (privacy policy, allergen chart, ...) is not a "pdf".
    for a in anchors:
        href = a["href"]
        if _is_pdf_href(href) and _pdf_is_relevant(a.get_text(" ", strip=True), href):
            return {"pattern": "pdf", "target": href}

    # 4. A location chooser that must be interacted with before content loads.
    if LOCATION_KEYWORDS.search(text):
        return {"pattern": "location_selector", "target": True}

    # 5. Happy-hour content sitting directly in the page text.
    if HH_KEYWORDS.search(text) and TIME_RANGE.search(text):
        return {"pattern": "inline", "target": None}

    # 6. An <img> whose src/alt/surrounding-anchor text hints at a menu or
    #    deal — some venues only post their happy hour as a photographed
    #    menu, not real text.
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        alt = img.get("alt", "")
        parent_a = img.find_parent("a")
        anchor_text = parent_a.get_text(" ", strip=True) if parent_a else ""
        anchor_href = parent_a.get("href", "") if parent_a else ""
        if _mentions_image_menu(src, alt, anchor_text, anchor_href):
            return {"pattern": "image_menu", "target": src}

    # 7. A QR-code shortlink (from a printed table card) whose own link text
    #    hints at a menu — these often redirect to a photographed menu image,
    #    or a webpage hosting one. handle_image_menu resolves the redirect.
    for a in anchors:
        href = a["href"]
        if _is_qr_shortlink(href) and _shortlink_mentions_menu(a.get_text(" ", strip=True)):
            return {"pattern": "image_menu", "target": href}

    return {"pattern": "none", "target": None}


async def load_page(url: str) -> dict | None:
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await _goto(page, url)
            await _bypass_age_gate(page, "[scraper]")
            html = await page.content()
            text = _relevant_window(await page.inner_text("body"))
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
        await _goto(page, url)
        await _bypass_age_gate(page, "[handle_link]")
        text = _relevant_window(await page.inner_text("body"))
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


GEMINI_IMAGE_PROMPT = (
    "You are extracting happy hour or food/drink deal information from a "
    "restaurant menu image. Extract all deals, times, and days visible in "
    "the image. If no deal information is present, return null."
)

# Extensions that mark a resolved URL as a direct image, vs. a webpage that
# needs to be screenshotted instead (e.g. a QR shortlink landing on a page
# that merely displays the menu image, banners and all).
IMAGE_URL_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def _is_image_url(url: str) -> bool:
    return url.split("?")[0].split("#")[0].lower().endswith(IMAGE_URL_EXTENSIONS)


async def _send_to_gemini(image_bytes: bytes, mime_type: str, label: str) -> str | None:
    try:
        client_ai = genai.Client(api_key=GEMINI_API_KEY)
        result = await client_ai.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                GEMINI_IMAGE_PROMPT,
                genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
        )
        result_text = (result.text or "").strip()
    except Exception as e:
        print(f"[handle_image_menu] FAIL {label} - Gemini error: {type(e).__name__}: {e}")
        return None

    if not result_text or result_text.lower().rstrip(".") == "null":
        print(f"[handle_image_menu] OK   {label} - no deal info found")
        return None

    print(f"[handle_image_menu] OK   {label}")
    return result_text


async def handle_image_menu(image_url: str) -> str | None:
    if not GEMINI_API_KEY:
        print(f"[handle_image_menu] FAIL {image_url} - GEMINI_API_KEY not configured")
        return None

    # Step 1: follow the URL with a real browser — a QR shortlink may bounce
    # through several redirects before landing on either an image or a page.
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            try:
                await _goto(page, image_url)
            except (PlaywrightTimeoutError, PlaywrightError) as e:
                print(f"[handle_image_menu] FAIL {image_url} - navigation error: {type(e).__name__}: {str(e).splitlines()[0]}")
                return None

            final_url = page.url

            if _is_image_url(final_url):
                # Step 2: resolved straight to an image file — download it directly.
                try:
                    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                        response = await client.get(final_url)
                        response.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[handle_image_menu] FAIL {image_url} - download error: {e}")
                    return None
                content_type = response.headers.get("content-type", "").split(";")[0].strip()
                if not content_type.startswith("image/"):
                    print(f"[handle_image_menu] FAIL {image_url} - not an image (content-type: {content_type or 'unknown'})")
                    return None
                image_bytes = response.content
                mime_type = content_type
            else:
                # Step 3: resolved to a webpage (e.g. a QR landing page showing
                # the menu inline) — screenshot the full page instead.
                try:
                    image_bytes = await page.screenshot(full_page=True)
                except PlaywrightError as e:
                    print(f"[handle_image_menu] FAIL {image_url} - screenshot error: {type(e).__name__}: {str(e).splitlines()[0]}")
                    return None
                mime_type = "image/png"
        finally:
            await browser.close()

    # Step 4: send whichever image bytes we ended up with to Gemini.
    return await _send_to_gemini(image_bytes, mime_type, image_url)


async def handle_location_selector(browser: Browser, base_url: str) -> str | None:
    page = await browser.new_page()
    try:
        await _goto(page, base_url)
        await _bypass_age_gate(page, "[handle_location_selector]")

        option = page.locator(
            "a[href*='location' i], button:has-text('location'), "
            "[class*='location' i] a, select option:nth-child(2)"
        ).first
        if await option.count() == 0:
            print(f"[handle_location_selector] no location option found at {base_url}")
            return _relevant_window(await page.inner_text("body"))

        await option.click()
        await _settle(page)
        await _bypass_age_gate(page, "[handle_location_selector]")

        html = await page.content()
        text = _relevant_window(await page.inner_text("body"))

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


# Paths worth guessing when the homepage itself gives no signal — many sites
# keep their happy hour / specials info on a dedicated page that just isn't
# linked from anywhere detect_pattern() looks (nav menus buried in JS, etc).
COMMON_SUBPATHS = (
    "/happy-hour",
    "/happyhour",
    "/happy_hour",
    "/specials",
    "/drink-specials",
    "/drinks",
    "/menu",
    "/menus",
    "/food-and-drinks",
    "/deals",
    "/promotions",
    "/offers",
    "/events",
)

SUBPATH_KEYWORDS = ("happy hour", "specials", "deals", "discount", "$", "half off", "% off")


def _mentions_subpath_deal(text: str) -> bool:
    haystack = text.lower()
    return any(keyword in haystack for keyword in SUBPATH_KEYWORDS)


async def try_common_paths(browser: Browser, base_url: str) -> str | None:
    page = await browser.new_page()
    try:
        for path in COMMON_SUBPATHS:
            url = urljoin(base_url, path)
            try:
                response = await _goto(page, url)
            except (PlaywrightTimeoutError, PlaywrightError):
                continue

            # A soft-404 (many sites resolve any unknown path to a 200 status
            # error page) would otherwise slip through on status alone —
            # that's exactly what the keyword check below guards against.
            if response is None or response.status != 200:
                continue

            await _bypass_age_gate(page, "[try_common_paths]")
            text = await page.inner_text("body")
            if _mentions_subpath_deal(text):
                print(f"[try_common_paths] OK   {url}")
                return _relevant_window(text)

        print(f"[try_common_paths] FAIL {base_url} - no common subpath had deal content")
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

    if pattern == "inline":
        text = page_data["text"]
        return {"text": text, "pattern": pattern, "success": bool(text)}

    if pattern == "pdf":
        text = await handle_pdf(urljoin(url, target))
        return {"text": text or "", "pattern": pattern, "success": text is not None}

    if pattern == "image_menu":
        text = await handle_image_menu(urljoin(url, target))
        return {"text": text or "", "pattern": pattern, "success": text is not None}

    if pattern == "none":
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                subpath_text = await try_common_paths(browser, url)
            finally:
                await browser.close()
        if subpath_text:
            return {"text": subpath_text, "pattern": "subpath", "success": True}
        text = page_data["text"]
        return {"text": text, "pattern": pattern, "success": bool(text)}

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
