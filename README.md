# MIRI WatchEye

**AI Discourse Sentiment & Thesis Tracking Dashboard for Bluesky**

Monitor how AI safety arguments penetrate public discourse. Built as a demonstration for MIRI (Machine Intelligence Research Institute).

## Features

- **Sentiment Analysis** - Categorizes posts into 6 sentiment types (Positive/Hype, Neutral, Concerned-Mundane, Concerned-X-Risk, Dismissive, Anti-AI)
- **MIRI Thesis Tracking** - Tracks penetration of 10 core AI safety arguments (Orthogonality, Instrumental Convergence, Deceptive Alignment, etc.)
- **Topic Clustering** - 536 raw topics normalized to 30 canonical categories
- **Date Filtering** - Filter dashboard by specific date with post counts per day
- **Interactive Charts** - Click any chart segment to open filtered posts in modal view
- **Semantic Search** - Find posts by content across the dataset
- **Expandable Posts** - Click to expand truncated post text

## Data Pipeline

### 1. Fetch from Bluesky

```bash
cd backend
python bluesky_fetcher.py
```

Searches Bluesky firehose for AI-related keywords (AI safety, AGI, superintelligence, ChatGPT, Claude, OpenAI, Anthropic, existential risk, alignment, MIRI, etc.) via AT Protocol.

Output: `data/bluesky_posts.json`

### 2. Analyze with Gemini

```bash
python gemini_analyzer.py ../data/bluesky_posts.json ../data/analysis_results.json
```

Batch-processes posts through Gemini Flash 2.0 for:
- Sentiment classification
- Topic detection
- MIRI thesis alignment (supports/counters/mentions)
- Brief summary

Output: `data/analysis_results.json`

### 3. Normalize Topics

```bash
python topic_normalizer.py
```

Maps 536 raw topics to 30 canonical categories using AI-generated taxonomy.

Output: `data/analysis_normalized.json` (used by API server)

## Quick Start

### Prerequisites
- Python 3.11+, Node.js 18+
- Google AI API key (Gemini)
- Bluesky account

### Run Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
export GOOGLE_API_KEY=your_key
uvicorn api_server:app --reload --port 8000

# Frontend
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Visit `http://localhost:5173`

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/dashboard` | Aggregated stats, charts, top posts |
| `GET /api/posts` | Filtered post list |
| `GET /api/search?q=` | Semantic search |
| `GET /api/thesis/{id}` | Thesis detail with sample posts |

## Project Structure

```
miri-watcheye/
├── backend/
│   ├── api_server.py       # FastAPI endpoints
│   ├── bluesky_fetcher.py  # AT Protocol client
│   ├── gemini_analyzer.py  # LLM batch analysis
│   ├── topic_normalizer.py # Topic canonicalization
│   └── miri_theses.py      # Thesis taxonomy
├── frontend/
│   └── src/App.jsx         # React dashboard
├── data/
│   ├── bluesky_posts.json      # Raw fetched posts
│   ├── analysis_results.json   # Gemini analysis
│   ├── analysis_normalized.json # With canonical topics
│   └── topic_taxonomy.json     # Topic mapping rules
└── docker-compose.yml
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini API key |
| `BLUESKY_HANDLE` | Your Bluesky handle |
| `BLUESKY_PASSWORD` | Bluesky app password |
| `VITE_API_URL` | Backend URL (frontend) |

## License

Built for MIRI employee candidate evaluation.
