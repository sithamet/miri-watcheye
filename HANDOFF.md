# MIRI WatchEye - Claude Code Handoff

## 🚨 IMMEDIATE PRIORITIES (in order)

1. **Get credentials from Vitalii** - Bluesky handle/app-password + Google AI API key
2. **Fetch REAL data** - Current 15 posts are FAKE samples, need 500-2000+ real posts
3. **Run Gemini analysis** on fetched data
4. **Verify dashboard** displays correctly with real data
6. **Add persistence** to the data so it doesn't reset on container restart 
5. **Deploy** to miritest.psychothrone.com (if server ready)
6. **Submit** to duncan@intelligence.org by Jan 6th
---

## 🎯 Mission Context

**What this is:** A trial task for a MIRI communications analyst position. Vitalii is building a working proof-of-concept to demonstrate his ability to automate sentiment analysis that MIRI currently does manually (see their "AI Zeitgeyser" internal periodical).

**Deadline:** January 6th, 2026
**Compensation:** $150
**Submit to:** duncan@intelligence.org

**Why this matters:** MIRI manually tracks AI discourse sentiment across social media. This tool automates that process, specifically tracking whether MIRI's core arguments ("If We Build This, Everyone Dies" theses) are penetrating public consciousness.

---

## 📊 Gap Analysis: What Vitalii Expects vs Current State

| Requirement | Expected | Current | Status |
|-------------|----------|---------|--------|
| Data volume | 500-2000 posts | 15 fake posts | ❌ CRITICAL |
| Data source | Real Bluesky API | Hand-written samples | ❌ CRITICAL |
| Date range | 1-2 days configurable | Fake dates | ❌ |
| Thesis tracking | 10 MIRI theses | ✅ Implemented | ✅ |
| Sentiment analysis | 6 categories | ✅ Implemented | ✅ |
| UI/Dashboard | Working React app | ✅ Built & working | ✅ |
| Deployment | miritest.psychothrone.com | Not deployed | ⚠️ Pending |
| Semantic search | Nice-to-have (v2) | Not implemented | ⏸️ Deferred |

**Bottom line:** The architecture and UI are DONE. The critical gap is REAL DATA.

---

### Backend (Python/FastAPI)
- [x] `miri_theses.py` - Taxonomy of 10 MIRI theses with descriptions, keywords, counter-narratives
- [x] `bluesky_fetcher.py` - AT Protocol client to fetch posts by keyword search
- [x] `gemini_analyzer.py` - Batch analysis using Gemini Flash (sentiment, topics, thesis detection)
- [x] `api_server.py` - FastAPI REST API serving dashboard data
- [x] `requirements.txt` - Dependencies listed

### Frontend (React/Vite)
- [x] `App.jsx` - Full dashboard with charts (Recharts), post feed, thesis detail panel
- [x] `App.css` - Dark "command center" theme styling
- [x] Build working (`npm run build` succeeds)

### Infrastructure
- [x] `docker-compose.yml` - Multi-container setup
- [x] Dockerfiles for frontend and backend
- [x] nginx configs for production

### Demo Data
- [x] `data/bluesky_posts.json` - 15 sample posts (MANUALLY WRITTEN, not real)
- [x] `data/analysis_results.json` - Pre-analyzed results for demo

---

## ❌ What's NOT Done (Critical)

### 1. **REAL DATA FETCH** (⚠️ HIGHEST PRIORITY)

**THE CURRENT DATA IS FAKE.** I wrote 15 sample posts by hand just to make the UI work. This is completely inadequate for the actual deliverable.

**Vitalii wants MUCH MORE data.** Target volume:
- **Minimum:** 500+ posts
- **Ideal:** 1000-2000+ posts covering 2-3 days of discourse
- **Current:** 15 fake posts (UNACCEPTABLE for submission)

**To fetch real data:**
```bash
cd backend
export BLUESKY_HANDLE=your.handle.bsky.social
export BLUESKY_PASSWORD=your_app_password  # Use app password, not main!
export GOOGLE_API_KEY=your_gemini_key

# Fetch real posts
python bluesky_fetcher.py

# Analyze them (will take a while with 1000+ posts)
python gemini_analyzer.py ../data/bluesky_posts.json ../data/analysis_results.json
```

**The fetcher may need modifications to get enough data:**
- Increase `limit` parameter in search calls (currently 30 per keyword)
- Add more search keywords to `SEARCH_KEYWORDS` in `bluesky_fetcher.py`
- Extend date range (currently 2 days, might need 3-5)
- Consider multiple fetch runs with different keyword batches
- May need to paginate more aggressively (follow `cursor` in responses)

**Current keywords (12 total, MAY NEED EXPANSION):**
```python
SEARCH_KEYWORDS = [
    "AI safety", "AI alignment", "AGI", "superintelligence",
    "AI risk", "AI doom", "existential risk AI", "MIRI",
    "AI pause", "AI regulation", "Eliezer Yudkowsky", "AI x-risk"
]
```

**Consider adding:** "AI takeover", "AI extinction", "artificial general intelligence", "machine intelligence", "AI consciousness", "AI ethics", "OpenAI safety", "Anthropic", "DeepMind safety", "AI governance", "compute governance", "AI moratorium", "frontier AI", "transformative AI"

### 2. **Credentials Needed from Vitalii**
- Bluesky account handle + app password
- Google AI API key (Gemini)
- Domain for deployment (miritest.psychothrone.com mentioned)

### 3. **Date Range Parameter**
The spec says "ability to specify date range". The `bluesky_fetcher.py` has `since` and `until` params but they're not exposed in the API yet. Need to add:
```python
# In api_server.py, add endpoint or query params for date filtering
@app.get("/api/fetch")
async def trigger_fetch(
    days_back: int = 2,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    # Trigger new data fetch with date range
    pass
```

### 4. **Deployment to miritest.psychothrone.com**
- Docker containers ready but not deployed
- Need to set up:
  - Domain DNS pointing to server
  - SSL certificate (Let's Encrypt)
  - Password protection (htpasswd)
  - Environment variables on server

### 5. **Semantic Search** (Lower Priority - v2 feature)
The Notion spec mentions "semantic search over previously categorized content". This would require:
- Embedding posts with a model
- Vector store (ChromaDB, Pinecone, or similar)
- Search endpoint

Marked as deferrable in our discussion.

---

## 🔧 Technical Notes

### Bluesky API Quirks
- `atproto` Python package works well
- Search endpoint: `app.bsky.feed.search_posts`
- Rate limits: ~100 posts per request, need pagination via cursor
- Auth optional for search but recommended

### Gemini Analysis
- Using `gemini-2.0-flash-exp` for main analysis
- Batch size: 10 posts per API call (configurable in `gemini_analyzer.py`)
- Returns JSON array with sentiment, topics, thesis IDs, stance
- **Cost estimate:** ~$0.01-0.02 per 100 posts with Flash (very cheap)
- **Time estimate:** ~1-2 minutes per 100 posts (rate limited)
- **For 1000 posts:** Expect ~15-20 min analysis time, <$0.20 cost

### Data Flow
```
Bluesky API → bluesky_posts.json → Gemini Analysis → analysis_results.json → FastAPI → React Dashboard
```

### File Locations
```
/home/claude/miri-watcheye/
├── backend/
│   ├── api_server.py      # Main API - run with uvicorn
│   ├── bluesky_fetcher.py # Data collection script
│   ├── gemini_analyzer.py # LLM analysis script
│   └── miri_theses.py     # Thesis taxonomy (edit to add theses)
├── frontend/
│   └── src/App.jsx        # Main dashboard component
├── data/
│   ├── bluesky_posts.json     # Raw posts (REPLACE WITH REAL DATA)
│   └── analysis_results.json  # Analysis output (REGENERATE)
└── docker-compose.yml
```

### Running Locally
```bash
# Terminal 1 - Backend
cd backend
pip install -r requirements.txt
uvicorn api_server:app --reload --port 8000

# Terminal 2 - Frontend  
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## 📋 Immediate TODO for Claude Code

1. **Get credentials from Vitalii** (Bluesky + Gemini API keys)

2. **Fetch real data:**
   ```bash
   cd /path/to/miri-watcheye/backend
   python bluesky_fetcher.py [handle] [password]
   ```

3. **Run analysis:**
   ```bash
   python gemini_analyzer.py ../data/bluesky_posts.json ../data/analysis_results.json
   ```

4. **Verify dashboard shows real data:**
   ```bash
   uvicorn api_server:app --port 8000
   # Check http://localhost:8000/api/dashboard
   ```

5. **Deploy to server** (if Vitalii has server access ready)

6. **Optional improvements:**
   - Add date range picker to UI
   - Increase data volume (more keywords, longer time range)
   - Add "refresh data" button to dashboard

---

## 🎨 Design Decisions Made

- **Dark theme**: Matches "command center" / analyst tool aesthetic
- **Thesis tracking as core feature**: This is what differentiates from generic sentiment tools
- **Engagement-weighted sorting**: High-engagement posts surface first
- **Click-to-filter**: Clicking sentiment/thesis filters the view
- **Sample posts in thesis detail**: Shows actual supporting/countering quotes

---

## 📊 What the Dashboard Shows

1. **Header**: Total posts, X-Risk Penetration %, date range
2. **Sentiment Pie Chart**: 6 categories (hype, neutral, mundane concern, x-risk concern, dismissive, anti-AI tribal)
3. **Thesis Bar Chart**: Which MIRI arguments appear, click for details
4. **Topic Distribution**: What people are discussing
5. **Post Feed**: Searchable, filterable list with engagement metrics

---

## ⚠️ Known Issues

1. **Recharts warning**: Bundle size warning during build (not critical)
2. **Protobuf conflict**: pip shows conflict with mediapipe (doesn't affect functionality)
3. **No persistence**: Data lives in JSON files, resets on container restart
4. **No auth on API**: Production should add authentication

---

## 💡 Vitalii's Preferences (from memory)

- Prefers direct, technical communication
- Has Gemini API access (used at Litero)
- Comfortable with Docker deployment
- Domain miritest.psychothrone.com mentioned for deployment

---

## 🔗 Key Resources

- MIRI "If Anyone Builds It" book: https://ai-frontiers.org/articles/summary-of-if-anyone-builds-it-everyone-dies
- Bluesky API docs: https://docs.bsky.app
- Gemini API: https://ai.google.dev
- Original Notion spec: Conversation history has full details

---

**Good luck! The foundation is solid - main work is getting real data flowing and deployed.**