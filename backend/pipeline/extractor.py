import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL = "openai/gpt-oss-20b"
MAX_INPUT_CHARS = 2_000

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_CONFIDENCE = {"high", "medium", "low"}
_SOURCE = {"website", "reviews", "both"}
_DEAL_TYPE = {"happy_hour", "lunch_special", "late_night", "weekday_deal", "early_bird", "other"}

SYSTEM_PROMPT = (
    "You are a data extraction engine that identifies recurring, time-based dining and "
    "drink deals from restaurant and bar website text.\n\n"
    "Return ONLY a single valid JSON object and nothing else. Do not include any "
    "explanation, preamble, or markdown code fences (no ```). The first character of "
    "your response must be '{' and the last must be '}'.\n\n"
    "A deal is any recurring discounted or special pricing tied to specific hours or days. "
    "Classify each into one deal_type:\n"
    "- happy_hour: discounted drinks and/or food during a set window.\n"
    "- lunch_special: a set-price or discounted menu during lunch hours.\n"
    "- late_night: deals available late, roughly after 9pm or 10pm.\n"
    "- weekday_deal: a recurring discount tied to specific weekday(s).\n"
    "- early_bird: discounts for dining before a certain time.\n"
    "- other: a time-based deal that fits none of the above.\n\n"
    "Use exactly this schema:\n"
    "{\n"
    '  "has_deal": boolean,\n'
    '  "deal_type": "happy_hour" | "lunch_special" | "late_night" | "weekday_deal" | "early_bird" | "other",\n'
    '  "days": ["Monday", "Tuesday", ...],\n'
    '  "start_time": "HH:MM" (24-hour) or null,\n'
    '  "end_time": "HH:MM" (24-hour) or null,\n'
    '  "deals": ["$12 burger + fries", "$5 margaritas", ...],\n'
    '  "confidence": "high" | "medium" | "low",\n'
    '  "source": "website" | "reviews" | "both",\n'
    '  "notes": string or null\n'
    "}\n\n"
    "Rules:\n"
    "- If the text contains no time-based deal, set has_deal to false, deal_type to "
    '"other", days and deals to empty arrays, start_time/end_time/notes to null, '
    'confidence to "low", and source to "website".\n'
    "- Only one deal is stored per venue, so when several are present pick the single most "
    "prominent one and set deal_type accordingly (note the others in notes if useful).\n"
    "- Use full weekday names. Expand ranges like \"Mon-Fri\" into each individual day.\n"
    '- Times must be 24-hour zero-padded HH:MM. Convert "3pm" to "15:00", "4:30 PM" to "16:30".\n'
    "- deals are short human-readable strings drawn from the text.\n"
    '- source is where the info came from: "website" for official site copy or menus, '
    '"reviews" for customer review text, "both" if mixed.\n'
    "- Set confidence using this guidance:\n"
    "  * high: explicit days AND times AND at least one specific deal are clearly stated.\n"
    "  * medium: a deal is clearly present but some detail (days, times, or deals) is "
    "missing or vague.\n"
    "  * low: only a passing or ambiguous mention with little concrete detail.\n"
    "- IMPORTANT: A deal may be described WITHOUT an explicit label like \"happy hour\". "
    "Set has_deal to true and extract the details whenever you see any of the following:\n"
    "  * Time-based pricing, e.g. \"3pm-6pm $3 beers\" or \"$5 wells until 7pm\".\n"
    '  * "Daily specials", "drink specials", "weekday deals", or similar recurring specials.\n'
    "  * Any discounted or reduced pricing tied to a specific time window.\n"
    "  * A set-price or discounted lunch menu during lunch hours.\n"
    '  * "Late night" specials that include a time range (e.g. "late night 10pm-close").\n'
    "  * Early-bird pricing for dining before a certain time.\n"
    "  Capture the days, time window, and discounted items into days/start_time/end_time/deals.\n"
)

STRICT_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + "\nIMPORTANT: Your previous output could not be parsed. Output MUST be a single "
    "raw JSON object with no surrounding text, no markdown, and no code fences. "
    "Return only the JSON object."
)


def _build_user_content(text: str, venue_name: str) -> str:
    snippet = text[:MAX_INPUT_CHARS]
    return f"Venue name: {venue_name}\n\nScraped text:\n{snippet}"


def _call_groq(client: Groq, system_prompt: str, user_content: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=1000,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content


def _validate(parsed: object) -> bool:
    if not isinstance(parsed, dict):
        return False
    if not isinstance(parsed.get("has_deal"), bool):
        return False
    if not parsed["has_deal"]:
        return True

    for key in ("deal_type", "days", "start_time", "end_time", "deals", "confidence", "source", "notes"):
        if key not in parsed:
            return False
    if parsed["deal_type"] not in _DEAL_TYPE:
        return False
    if not (isinstance(parsed["days"], list) and all(isinstance(d, str) for d in parsed["days"])):
        return False
    if not (isinstance(parsed["deals"], list) and all(isinstance(d, str) for d in parsed["deals"])):
        return False
    for t in (parsed["start_time"], parsed["end_time"]):
        if t is not None and not (isinstance(t, str) and _TIME_RE.match(t)):
            return False
    if parsed["confidence"] not in _CONFIDENCE:
        return False
    if parsed["source"] not in _SOURCE:
        return False
    if not (parsed["notes"] is None or isinstance(parsed["notes"], str)):
        return False
    return True


def _parse_and_validate(content: str) -> dict | None:
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if _validate(parsed) else None


def extract_happy_hour(text: str, venue_name: str) -> dict | None:
    if not text or not text.strip():
        return None

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    user_content = _build_user_content(text, venue_name)

    parsed = _parse_and_validate(_call_groq(client, SYSTEM_PROMPT, user_content))
    if parsed is None:
        # Retry once with a stricter prompt before giving up.
        parsed = _parse_and_validate(_call_groq(client, STRICT_SYSTEM_PROMPT, user_content))

    if parsed is None or not parsed["has_deal"]:
        return None
    return parsed


if __name__ == "__main__":
    import sys

    sample = sys.stdin.read() if not sys.stdin.isatty() else "Happy Hour Mon-Fri 3pm-6pm, $4 drafts and $6 margaritas."
    result = extract_happy_hour(sample, venue_name="CLI Test Venue")
    print(json.dumps(result, indent=2))
