# Cincin

> *Cincin* — Italian for "cheers"

**Cincin** is an AI-powered happy hour aggregator for Phoenix, AZ. Instead of digging through outdated Yelp pages or bar websites, Cincin automatically finds, extracts, and surfaces happy hour deals near you — in real time.

---

## What It Does

- **Location-based search** — find happy hours near you or any address
- **AI extraction pipeline** — GPT-4o scrapes and parses unstructured bar websites, menus, and reviews into clean, structured deal data
- **"On now" filter** — see only the happy hours happening right this moment
- **Map view** — visualize venues on an interactive Mapbox map with color-coded pins
- **Weekly refresh** — pipeline re-scrapes venues automatically to keep data fresh

---

## Tech Stack

### Frontend
- [Next.js 14](https://nextjs.org/) — React framework
- [Tailwind CSS](https://tailwindcss.com/) — styling
- [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/) — interactive map

### Backend
- [FastAPI](https://fastapi.tiangolo.com/) — Python REST API
- [PostgreSQL](https://www.postgresql.org/) + [PostGIS](https://postgis.net/) — geospatial database
- [SQLAlchemy](https://www.sqlalchemy.org/) — ORM

### AI Pipeline
- [GPT-4o](https://openai.com/) — happy hour data extraction from unstructured text
- [Playwright](https://playwright.dev/python/) — headless browser scraping
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF menu parsing
- [Google Places API](https://developers.google.com/maps/documentation/places/web-service) — venue seeding

### Deployment
- [Vercel](https://vercel.com/) — frontend hosting
- [Railway](https://railway.app/) — backend + database hosting

---

## How the AI Pipeline Works

```
Google Places API
      ↓
  Venue DB (name, address, website)
      ↓
  Playwright Scraper
      ↓
Pattern Detection:
  ├── "link"              → follow happy hour page link
  ├── "location_selector" → interact with location modal first
  ├── "pdf"               → download & parse with PyMuPDF
  └── "inline"            → extract text directly from homepage
      ↓
  GPT-4o Extraction
      ↓
  Structured JSON (days, times, deals, confidence score)
      ↓
  PostgreSQL + PostGIS
      ↓
  Served via FastAPI → Next.js frontend
```

---

## Getting Started

### Prerequisites
- Node.js 20+
- Python 3.11+
- PostgreSQL with PostGIS extension
- Git

### 1. Clone the repo
```bash
git clone https://github.com/hridiukani/cincin.git
cd cincin
```

### 2. Set up the backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
```

### 3. Run database migrations
```bash
psql -U cincin -d cincin -f db/migrations/001_initial.sql
```

### 4. Seed venues from Google Places
```bash
python scripts/seed_venues.py
```

### 5. Run the AI scraping pipeline
```bash
python pipeline/runner.py --limit 10  # test on 10 venues first
```

### 6. Start the backend
```bash
uvicorn main:app --reload
```

### 7. Set up the frontend
```bash
cd ../frontend
npm install
cp .env.example .env.local
# Fill in your Mapbox token and API URL
npm run dev
```

Frontend runs at `http://localhost:3000`, backend at `http://localhost:8000`.

---

## Environment Variables

### Backend (`/backend/.env`)
```
DATABASE_URL=postgresql://cincin:cincin123@localhost:5432/cincin
OPENAI_API_KEY=your_openai_key
GOOGLE_PLACES_API_KEY=your_google_places_key
```

### Frontend (`/frontend/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token
```

---

## Deployment

| Service | Platform | Notes |
|---|---|---|
| Frontend | Vercel | Auto-deploys from `main` branch |
| Backend | Railway | Set env vars in Railway dashboard |
| Database | Railway PostgreSQL | Enable PostGIS extension after provisioning |

---

## Project Structure

```
cincin/
├── frontend/               # Next.js app
│   ├── app/                # App router pages
│   ├── components/         # React components
│   └── public/             # Static assets
├── backend/                # FastAPI app
│   ├── api/                # Route handlers
│   ├── db/                 # Models, migrations
│   ├── pipeline/           # Scraper + extractor
│   └── scripts/            # Venue seeder, utilities
└── README.md
```

---

## Built By

**Hridi Ukani** — [LinkedIn](https://linkedin.com/in/hridiukani1807) · [GitHub](https://github.com/hridiukani) · [Portfolio](https://hridiukani.vercel.app)

---

*Cincin is currently live for Phoenix, AZ. More cities coming soon.*