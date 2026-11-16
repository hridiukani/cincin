# Matches the Playwright version pinned in requirements.txt — this base image
# already bundles the matching Chromium build and all its system libraries
# (avoids the libasound2/etc. dependency hell of installing Playwright on a
# bare Python image), so no separate `playwright install` step is needed.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT at runtime; shell form so it actually expands.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
