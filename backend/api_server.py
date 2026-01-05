"""
MIRI WatchEye API Server
Serves analyzed Bluesky data for the dashboard.
"""

import os
import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from miri_theses import MIRI_THESES, SENTIMENT_CATEGORIES
from gemini_analyzer import GeminiAnalyzer, cosine_similarity


# Data paths
DATA_DIR = Path(__file__).parent.parent / "data"
POSTS_FILE = DATA_DIR / "bluesky_posts.json"
ANALYSIS_FILE = DATA_DIR / "analysis_results.json"
NORMALIZED_FILE = DATA_DIR / "analysis_normalized.json"
TAXONOMY_FILE = DATA_DIR / "topic_taxonomy.json"


app = FastAPI(
    title="MIRI WatchEye API",
    description="AI discourse sentiment & thesis tracking on Bluesky",
    version="0.1.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class SentimentSummary(BaseModel):
    category: str
    name: str
    count: int
    percentage: float


class ThesisSummary(BaseModel):
    id: str
    name: str
    short: str
    mention_count: int
    mention_percentage: float  # % of all posts mentioning this thesis
    support_count: int
    counter_count: int
    neutral_count: int


class TopicSummary(BaseModel):
    topic: str
    count: int
    percentage: float


class PostSummary(BaseModel):
    uri: str
    author: str
    text: str
    sentiment: str
    topics: list[str]
    theses: list[str]
    thesis_stance: str
    engagement: float
    likes: int
    reposts: int
    replies: int
    web_url: str
    created_at: str
    summary: str


class DateInfo(BaseModel):
    date: str
    count: int


class DashboardData(BaseModel):
    total_posts: int
    date_range: dict
    available_dates: list[DateInfo]  # Dates with data
    sentiment_distribution: list[SentimentSummary]
    thesis_tracking: list[ThesisSummary]
    topic_distribution: list[TopicSummary]
    top_posts: list[PostSummary]
    xrisk_penetration: float  # % of posts engaging with x-risk themes


def load_data():
    """Load posts and analysis data (prefer normalized if available)."""
    posts = []
    analyses = []

    if POSTS_FILE.exists():
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            posts = json.load(f)

    # Prefer normalized data if available
    analysis_file = NORMALIZED_FILE if NORMALIZED_FILE.exists() else ANALYSIS_FILE
    if analysis_file.exists():
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analyses = json.load(f)

    return posts, analyses


def load_taxonomy():
    """Load topic taxonomy."""
    if TAXONOMY_FILE.exists():
        with open(TAXONOMY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"canonical_topics": [], "mapping": {}}


def merge_data(posts: list, analyses: list) -> list[dict]:
    """Merge posts with their analyses."""
    analysis_lookup = {a['uri']: a for a in analyses}

    merged = []
    for post in posts:
        analysis = analysis_lookup.get(post['uri'], {})
        merged.append({
            **post,
            **analysis
        })

    return merged


def is_ai_relevant(post: dict) -> bool:
    """Check if post is AI-related (not tagged as 'not_ai_related')."""
    topics = post.get('topics_normalized', [])
    return 'not_ai_related' not in topics


@app.get("/")
async def root():
    return {"message": "MIRI WatchEye API", "status": "running"}


@app.get("/api/config")
async def get_config():
    """Get configuration data (theses, categories, etc.)"""
    taxonomy = load_taxonomy()
    return {
        "theses": [
            {
                "id": t["id"],
                "name": t["name"],
                "short": t["short"],
                "description": t["description"].strip()
            }
            for t in MIRI_THESES
        ],
        "sentiment_categories": SENTIMENT_CATEGORIES,
        "canonical_topics": taxonomy.get("canonical_topics", [])
    }


@app.get("/api/taxonomy")
async def get_taxonomy():
    """Get topic taxonomy with canonical topics and mappings."""
    return load_taxonomy()


@app.get("/api/dashboard", response_model=DashboardData)
async def get_dashboard(
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)")
):
    """Get main dashboard data, optionally filtered by date range."""
    posts, analyses = load_data()

    if not posts or not analyses:
        raise HTTPException(status_code=404, detail="No data available")

    merged = merge_data(posts, analyses)

    # Compute available dates from ALL data (before filtering)
    all_dates = [p.get('created_at', '')[:10] for p in merged if p.get('created_at')]
    date_counts = {}
    for d in all_dates:
        date_counts[d] = date_counts.get(d, 0) + 1
    available_dates = [
        DateInfo(date=d, count=c)
        for d, c in sorted(date_counts.items())
    ]

    # Apply date filter if specified
    if start_date or end_date:
        def in_date_range(post):
            created = post.get('created_at', '')[:10]
            if not created:
                return False
            if start_date and created < start_date:
                return False
            if end_date and created > end_date:
                return False
            return True
        merged = [p for p in merged if in_date_range(p)]

    total = len(merged)

    # Date range (of filtered data)
    dates = [p.get('created_at', '') for p in merged if p.get('created_at')]
    date_range = {
        "start": min(dates) if dates else None,
        "end": max(dates) if dates else None
    }
    
    # Sentiment distribution
    sentiment_counts = {}
    for item in merged:
        s = item.get('sentiment', 'neutral_informative')
        sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
    
    sentiment_distribution = []
    for cat in SENTIMENT_CATEGORIES:
        count = sentiment_counts.get(cat['id'], 0)
        sentiment_distribution.append(SentimentSummary(
            category=cat['id'],
            name=cat['name'],
            count=count,
            percentage=100 * count / total if total > 0 else 0
        ))
    
    # Thesis tracking
    thesis_mentions = {t['id']: {'mention': 0, 'support': 0, 'counter': 0, 'neutral': 0} for t in MIRI_THESES}
    for item in merged:
        theses = item.get('miri_theses', [])
        stance = item.get('miri_thesis_alignment', 'unrelated')
        for thesis_id in theses:
            if thesis_id in thesis_mentions:
                thesis_mentions[thesis_id]['mention'] += 1
                if stance == 'supports':
                    thesis_mentions[thesis_id]['support'] += 1
                elif stance == 'counters':
                    thesis_mentions[thesis_id]['counter'] += 1
                else:
                    thesis_mentions[thesis_id]['neutral'] += 1
    
    thesis_tracking = []
    for t in MIRI_THESES:
        counts = thesis_mentions[t['id']]
        mention_pct = 100 * counts['mention'] / total if total > 0 else 0
        thesis_tracking.append(ThesisSummary(
            id=t['id'],
            name=t['name'],
            short=t['short'],
            mention_count=counts['mention'],
            mention_percentage=round(mention_pct, 2),
            support_count=counts['support'],
            counter_count=counts['counter'],
            neutral_count=counts['neutral']
        ))

    # Sort by mention count
    thesis_tracking.sort(key=lambda x: -x.mention_count)
    
    # Topic distribution (prefer normalized topics)
    topic_counts = {}
    taxonomy = load_taxonomy()
    canonical_lookup = {t['id']: t['name'] for t in taxonomy.get('canonical_topics', [])}

    for item in merged:
        # Use normalized topics if available, fallback to raw topics
        topics = item.get('topics_normalized', item.get('topics', []))
        for topic in topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    # Filter out "Not AI Related" from topic distribution
    topic_distribution = [
        TopicSummary(
            topic=canonical_lookup.get(topic, topic),  # Use human-readable name
            count=count,
            percentage=100 * count / total if total > 0 else 0
        )
        for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1])
        if topic != 'not_ai_related'  # Exclude from chart
    ]

    # Top posts by engagement (only AI-relevant posts)
    ai_relevant_posts = [p for p in merged if is_ai_relevant(p)]
    sorted_posts = sorted(ai_relevant_posts, key=lambda x: x.get('engagement_score', 0), reverse=True)
    top_posts = [
        PostSummary(
            uri=p['uri'],
            author=p.get('author_display_name', p.get('author_handle', 'Unknown')),
            text=p.get('text', ''),  # Full text for frontend truncation
            sentiment=p.get('sentiment', 'neutral_informative'),
            topics=[canonical_lookup.get(t, t) for t in p.get('topics_normalized', p.get('topics', []))],
            theses=p.get('miri_theses', []),
            thesis_stance=p.get('miri_thesis_alignment', 'unrelated'),
            engagement=p.get('engagement_score', 0),
            likes=p.get('likes', 0),
            reposts=p.get('reposts', 0),
            replies=p.get('replies', 0),
            web_url=p.get('web_url', ''),
            created_at=p.get('created_at', ''),
            summary=p.get('summary', '')
        )
        for p in sorted_posts[:50]
    ]
    
    # X-risk penetration: % of posts with x-risk related sentiment or theses
    xrisk_count = sum(
        1 for item in merged
        if item.get('sentiment') == 'concerned_xrisk'
        or any(t in ['default_doom', 'alignment_hard', 'no_warning_shot', 'pause_needed']
               for t in item.get('miri_theses', []))
    )
    xrisk_penetration = 100 * xrisk_count / total if total > 0 else 0
    
    return DashboardData(
        total_posts=total,
        date_range=date_range,
        available_dates=available_dates,
        sentiment_distribution=sentiment_distribution,
        thesis_tracking=thesis_tracking,
        topic_distribution=topic_distribution,
        top_posts=top_posts,
        xrisk_penetration=xrisk_penetration
    )


@app.get("/api/posts")
async def get_posts(
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    thesis: Optional[str] = Query(None, description="Filter by thesis"),
    topic: Optional[str] = Query(None, description="Filter by topic (canonical ID or name)"),
    search: Optional[str] = Query(None, description="Search in text"),
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Get filtered posts."""
    posts, analyses = load_data()
    merged = merge_data(posts, analyses)

    # Load taxonomy for topic name lookup
    taxonomy = load_taxonomy()
    canonical_lookup = {t['id']: t['name'] for t in taxonomy.get('canonical_topics', [])}
    name_to_id = {t['name'].lower(): t['id'] for t in taxonomy.get('canonical_topics', [])}

    # Apply filters - start with only AI-relevant posts
    filtered = [p for p in merged if is_ai_relevant(p)]

    # Date filter
    if start_date or end_date:
        def in_date_range(post):
            created = post.get('created_at', '')[:10]
            if not created:
                return False
            if start_date and created < start_date:
                return False
            if end_date and created > end_date:
                return False
            return True
        filtered = [p for p in filtered if in_date_range(p)]

    if sentiment:
        filtered = [p for p in filtered if p.get('sentiment') == sentiment]

    if thesis:
        filtered = [p for p in filtered if thesis in p.get('miri_theses', [])]

    if topic:
        # Support filtering by either canonical ID or name
        topic_lower = topic.lower()
        topic_id = name_to_id.get(topic_lower, topic)  # Convert name to ID if possible
        filtered = [
            p for p in filtered
            if topic_id in p.get('topics_normalized', [])
            or topic in p.get('topics_normalized', [])
            or topic in p.get('topics', [])
        ]

    if search:
        search_lower = search.lower()
        filtered = [p for p in filtered if search_lower in p.get('text', '').lower()]

    # Sort by engagement
    filtered.sort(key=lambda x: x.get('engagement_score', 0), reverse=True)

    # Paginate
    total = len(filtered)
    filtered = filtered[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "posts": [
            PostSummary(
                uri=p['uri'],
                author=p.get('author_display_name', p.get('author_handle', 'Unknown')),
                text=p.get('text', ''),  # Full text for frontend truncation
                sentiment=p.get('sentiment', 'neutral_informative'),
                topics=[canonical_lookup.get(t, t) for t in p.get('topics_normalized', p.get('topics', []))],
                theses=p.get('miri_theses', []),
                thesis_stance=p.get('miri_thesis_alignment', 'unrelated'),
                engagement=p.get('engagement_score', 0),
                likes=p.get('likes', 0),
                reposts=p.get('reposts', 0),
                replies=p.get('replies', 0),
                web_url=p.get('web_url', ''),
                created_at=p.get('created_at', ''),
                summary=p.get('summary', '')
            )
            for p in filtered
        ]
    }


@app.get("/api/thesis/{thesis_id}")
async def get_thesis_detail(thesis_id: str):
    """Get detailed info about a specific thesis and related posts."""
    # Find thesis
    thesis = next((t for t in MIRI_THESES if t['id'] == thesis_id), None)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")
    
    posts, analyses = load_data()
    merged = merge_data(posts, analyses)
    
    # Filter to posts mentioning this thesis
    related = [p for p in merged if thesis_id in p.get('miri_theses', [])]
    
    # Group by stance
    supporting = [p for p in related if p.get('miri_thesis_alignment') == 'supports']
    countering = [p for p in related if p.get('miri_thesis_alignment') == 'counters']
    neutral = [p for p in related if p.get('miri_thesis_alignment') not in ['supports', 'counters']]
    
    return {
        "thesis": {
            "id": thesis['id'],
            "name": thesis['name'],
            "short": thesis['short'],
            "description": thesis['description'].strip(),
            "keywords": thesis['keywords'],
            "counter_narratives": thesis['counter_narratives']
        },
        "stats": {
            "total_mentions": len(related),
            "supporting": len(supporting),
            "countering": len(countering),
            "neutral": len(neutral)
        },
        "sample_supporting": [
            {"text": p['text'][:300], "author": p.get('author_handle'), "url": p.get('web_url')}
            for p in sorted(supporting, key=lambda x: -x.get('engagement_score', 0))[:5]
        ],
        "sample_countering": [
            {"text": p['text'][:300], "author": p.get('author_handle'), "url": p.get('web_url')}
            for p in sorted(countering, key=lambda x: -x.get('engagement_score', 0))[:5]
        ]
    }


# Lazy-loaded analyzer for semantic search
_analyzer: Optional[GeminiAnalyzer] = None


def get_analyzer() -> GeminiAnalyzer:
    """Get or create analyzer instance (for embeddings)."""
    global _analyzer
    if _analyzer is None:
        try:
            _analyzer = GeminiAnalyzer()
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Analyzer not configured: {e}")
    return _analyzer


@app.get("/api/search")
async def semantic_search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Max results")
):
    """
    Semantic search across posts using embeddings.
    Finds posts similar in meaning to the query.
    """
    posts, analyses = load_data()

    if not analyses:
        raise HTTPException(status_code=404, detail="No analysis data available")

    # Load taxonomy for topic name lookup
    taxonomy = load_taxonomy()
    canonical_lookup = {t['id']: t['name'] for t in taxonomy.get('canonical_topics', [])}

    def format_result(p, similarity=1.0):
        """Format a post result consistently with PostSummary."""
        return {
            "uri": p.get('uri') or p.get('id', ''),
            "author": p.get('author_display_name', p.get('author_handle', 'Unknown')),
            "text": p.get('text', ''),
            "sentiment": p.get('sentiment', 'neutral_informative'),
            "topics": [canonical_lookup.get(t, t) for t in p.get('topics_normalized', p.get('topics', []))],
            "theses": p.get('miri_theses', []),
            "thesis_stance": p.get('miri_thesis_alignment', 'unrelated'),
            "engagement": p.get('engagement_score', 0),
            "likes": p.get('likes', 0),
            "reposts": p.get('reposts', 0),
            "replies": p.get('replies', 0),
            "web_url": p.get('web_url', ''),
            "created_at": p.get('created_at', ''),
            "summary": p.get('summary', ''),
            "similarity": round(similarity, 4)
        }

    # Filter to posts with embeddings
    with_embeddings = [a for a in analyses if a.get('embedding')]

    if not with_embeddings:
        # Fallback to text search if no embeddings
        merged = merge_data(posts, analyses)
        q_lower = q.lower()
        results = [
            p for p in merged
            if is_ai_relevant(p)  # Only AI-relevant posts
            and (q_lower in p.get('text', '').lower()
                 or q_lower in p.get('summary', '').lower()
                 or any(q_lower in t.lower() for t in p.get('topics', [])))
        ]
        results.sort(key=lambda x: x.get('engagement_score', 0), reverse=True)
        return {
            "query": q,
            "search_type": "text_fallback",
            "total": len(results),
            "results": [format_result(p) for p in results[:limit]]
        }

    # Use semantic search with embeddings
    try:
        analyzer = get_analyzer()
        query_embedding = analyzer.embed_query(q)

        if not query_embedding:
            raise HTTPException(status_code=500, detail="Failed to embed query")

        # Score all posts by similarity
        scored = []
        post_lookup = {p['uri']: p for p in posts}

        for analysis in with_embeddings:
            sim = cosine_similarity(query_embedding, analysis['embedding'])
            post = post_lookup.get(analysis.get('id') or analysis.get('uri'), {})
            scored.append({
                **post,
                **analysis,
                'similarity': sim
            })

        # Sort by similarity and filter out non-AI posts
        scored.sort(key=lambda x: -x['similarity'])
        ai_relevant_results = [p for p in scored if is_ai_relevant(p)]

        return {
            "query": q,
            "search_type": "semantic",
            "total": len(ai_relevant_results),
            "results": [format_result(p, p['similarity']) for p in ai_relevant_results[:limit]]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
