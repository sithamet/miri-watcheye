"""
Gemini-powered Post Analyzer with RAG and Dynamic Topic Discovery
Analyzes Bluesky posts for sentiment, dynamic topics, and MIRI thesis alignment.
Uses embeddings for RAG-enhanced analysis and semantic search.

Features:
- Incremental saving after each batch (crash-safe)
- Resume capability (skips already-analyzed posts)
- Detailed logging with timestamps
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field
import google.generativeai as genai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

from miri_theses import (
    MIRI_THESES,
    SENTIMENT_CATEGORIES,
    get_thesis_prompt,
    get_sentiment_prompt,
)

# Load environment variables
load_dotenv()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


@dataclass
class PostAnalysis:
    """Analysis results for a single post."""
    uri: str
    text: str  # Original post text (for RAG)
    sentiment: str  # ID from SENTIMENT_CATEGORIES
    sentiment_confidence: float  # 0-1
    topics: list[str]  # Dynamic topic labels
    miri_theses: list[str]  # List of thesis IDs that post aligns with
    miri_thesis_alignment: str  # 'supports', 'counters', 'mentions', or 'unrelated'
    engagement_score: float  # Normalized engagement metric
    summary: str  # Brief summary of the post's stance
    embedding: list[float] = field(default_factory=list)  # Text embedding for RAG/search
    raw_analysis: dict = field(default_factory=dict)  # Full Gemini response


class GeminiAnalyzer:
    """Analyzes posts using Google Gemini with RAG-enhanced dynamic topic discovery."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize analyzer.

        Args:
            api_key: Google AI API key
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY required")

        genai.configure(api_key=self.api_key)

        # Use Flash for cost efficiency
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.embedding_model = "models/text-embedding-004"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed texts using Gemini embedding model.

        Args:
            texts: List of strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        try:
            # Batch embed (max 100 per request)
            embeddings = []
            for i in range(0, len(texts), 100):
                batch = texts[i:i+100]
                result = genai.embed_content(
                    model=self.embedding_model,
                    content=batch,
                    task_type="retrieval_document"
                )
                # Result is either a single embedding or list of embeddings
                if isinstance(result['embedding'][0], list):
                    embeddings.extend(result['embedding'])
                else:
                    embeddings.append(result['embedding'])

            return embeddings
        except Exception as e:
            print(f"Embedding error: {e}")
            # Return empty embeddings on failure
            return [[] for _ in texts]

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query (uses different task type)."""
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=query,
                task_type="retrieval_query"
            )
            return result['embedding']
        except Exception as e:
            print(f"Query embedding error: {e}")
            return []

    def find_similar_posts(
        self,
        text: str,
        existing_analyses: list[dict],
        top_k: int = 10
    ) -> list[dict]:
        """
        Find most similar already-analyzed posts using embeddings.

        Args:
            text: Text to find similar posts for
            existing_analyses: Previously analyzed posts with embeddings
            top_k: Number of similar posts to return

        Returns:
            List of similar post analyses
        """
        if not existing_analyses:
            return []

        # Filter to only posts with embeddings
        with_embeddings = [a for a in existing_analyses if a.get('embedding')]
        if not with_embeddings:
            return []

        # Embed query text
        query_emb = self.embed_query(text)
        if not query_emb:
            return []

        # Score all posts
        scored = []
        for item in with_embeddings:
            sim = cosine_similarity(query_emb, item['embedding'])
            scored.append((sim, item))

        # Sort by similarity and return top-k
        scored.sort(reverse=True, key=lambda x: x[0])
        return [item for _, item in scored[:top_k]]

    def _build_analysis_prompt(
        self,
        posts_batch: list[dict],
        similar_examples: list[dict] = None,
        existing_topics: list[str] = None
    ) -> str:
        """
        Build prompt for batch analysis with dynamic topics and RAG examples.

        Args:
            posts_batch: Posts to analyze
            similar_examples: Previously analyzed similar posts for RAG
            existing_topics: List of topics already discovered (for consistency)

        Returns:
            Prompt string
        """
        posts_json = json.dumps([
            {
                "id": p["uri"],
                "text": p["text"][:1000],  # Truncate long posts
                "author": p.get("author_handle", "unknown"),
                "likes": p.get("likes", 0),
                "reposts": p.get("reposts", 0),
                "replies": p.get("replies", 0)
            }
            for p in posts_batch
        ], indent=2)

        prompt = f"""Analyze these social media posts. For each post, determine:

1. **AI Relevance** - Is this post actually about AI/ML/LLMs?
   - If NOT about AI (false positive from search), set ai_relevant: false
   - If about AI, set ai_relevant: true

2. **Sentiment** - Which category best fits:
{get_sentiment_prompt()}

3. **Topics** - What SPECIFIC topics does this post discuss?

   FORBIDDEN TOPICS (too generic - NEVER use these):
   - "AI", "Artificial Intelligence", "Technology", "Tech", "Machine Learning"
   - "Art", "Social Media", "Internet", "News", "Politics"

   Topics must be SPECIFIC to the post content. Examples:
   - BAD: "AI" → GOOD: "ChatGPT memory feature", "OpenAI board drama"
   - BAD: "Art" → GOOD: "Midjourney v6 capabilities", "AI art copyright concerns"
   - BAD: "Jobs" → GOOD: "Software developer job automation fears"
   - BAD: "Safety" → GOOD: "AI alignment research", "Deepfake detection challenges"

   Prefer existing topics when they fit well, but create new SPECIFIC topics
   when needed. Better to have a specific new topic than force a generic match.

   Each post should have 1-3 SPECIFIC topics.

4. **MIRI Thesis Alignment** - Does the post express or engage with any of these AI safety arguments?
{get_thesis_prompt()}

5. **Thesis Stance** - If it engages with MIRI theses:
   - "supports" - agrees with or promotes the thesis
   - "counters" - argues against or dismisses the thesis
   - "mentions" - references without clear stance
   - "unrelated" - doesn't engage with safety theses

6. **Summary** - One sentence capturing the post's main point.
"""

        # Add existing topics (filter out generic ones)
        if existing_topics:
            generic_topics = {'ai', 'art', 'technology', 'tech', 'social media',
                           'internet', 'news', 'machine learning', 'artificial intelligence',
                           'politics', 'general ai discussion'}
            filtered = [t for t in existing_topics if t.lower() not in generic_topics]
            if filtered:
                topics_list = ", ".join(f'"{t}"' for t in filtered[:30])
                prompt += f"""

**EXISTING SPECIFIC TOPICS** (prefer these when they fit well):
[{topics_list}]
"""

        # Add RAG examples (show up to 15 for better context)
        if similar_examples:
            examples_text = "\n".join([
                f'- "{ex.get("text", "")[:200]}..."\n  → topics: {ex.get("topics", [])}, sentiment: {ex.get("sentiment", "?")}'
                for ex in similar_examples[:15]
            ])
            prompt += f"""

**SIMILAR POSTS FOR REFERENCE**:
{examples_text}
"""

        prompt += f"""

Return a JSON array with one object per post:
```json
[
  {{
    "id": "post_uri",
    "ai_relevant": true,
    "sentiment": "sentiment_id",
    "sentiment_confidence": 0.85,
    "topics": ["Specific Topic 1", "Specific Topic 2"],
    "miri_theses": ["thesis_id_1"],
    "thesis_stance": "supports|counters|mentions|unrelated",
    "summary": "Brief summary"
  }}
]
```

Important:
- Topics must be SPECIFIC - never use generic terms like "AI" or "Art"
- If post is NOT about AI, set ai_relevant: false and topics: ["Not AI Related"]
- Be precise with thesis detection - only mark theses that are clearly expressed
- Most casual posts will be "unrelated" to MIRI theses - that's expected
- For non-English posts, set ai_relevant: false

Posts to analyze:
{posts_json}

Return ONLY the JSON array, no other text."""

        return prompt

    def analyze_batch_with_rag(
        self,
        posts: list[dict],
        existing_analyses: list[dict] = None,
        batch_size: int = 10
    ) -> list[dict]:
        """
        Analyze posts with RAG enhancement - uses similar posts for context.

        Args:
            posts: List of post dictionaries
            existing_analyses: Previously analyzed posts for RAG
            batch_size: Posts per API call

        Returns:
            List of analysis result dictionaries with embeddings
        """
        results = []
        existing = existing_analyses or []

        for i in range(0, len(posts), batch_size):
            batch = posts[i:i+batch_size]

            # Find similar examples for RAG (from previously analyzed posts)
            similar_examples = []
            if existing:
                for post in batch:
                    similar = self.find_similar_posts(post['text'], existing, top_k=10)
                    for s in similar:
                        if s not in similar_examples:
                            similar_examples.append(s)

            # Deduplicate and limit examples
            similar_examples = similar_examples[:5]

            # Build RAG-enhanced prompt
            prompt = self._build_analysis_prompt(batch, similar_examples)

            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=4096
                    )
                )

                # Parse JSON from response
                text = response.text.strip()
                # Handle markdown code blocks
                if text.startswith('```'):
                    text = text.split('```')[1]
                    if text.startswith('json'):
                        text = text[4:]

                batch_results = json.loads(text)

                # Generate embeddings for the batch
                batch_texts = [p['text'] for p in batch]
                embeddings = self.embed_texts(batch_texts)

                # Add embeddings and original text to results
                for j, result in enumerate(batch_results):
                    result['embedding'] = embeddings[j] if j < len(embeddings) else []
                    result['text'] = batch[j]['text'] if j < len(batch) else ''

                results.extend(batch_results)

                # Add to existing for next batch's RAG
                existing.extend(batch_results)

                print(f"Analyzed batch {i//batch_size + 1}/{(len(posts)-1)//batch_size + 1}")

            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                print(f"Raw response: {response.text[:500]}...")
                # Return fallback results for this batch
                for j, post in enumerate(batch):
                    results.append({
                        "id": post["uri"],
                        "text": post["text"],
                        "sentiment": "neutral_informative",
                        "sentiment_confidence": 0.5,
                        "topics": ["General AI Discussion"],
                        "miri_theses": [],
                        "thesis_stance": "unrelated",
                        "summary": "Analysis failed",
                        "embedding": []
                    })
            except Exception as e:
                print(f"Error analyzing batch: {e}")
                time.sleep(5)  # Back off on errors

            # Rate limiting
            time.sleep(1)

        return results

    def analyze_posts(
        self,
        posts: list,
        existing_analyses: list[dict] = None
    ) -> list[PostAnalysis]:
        """
        Analyze posts and return structured results with RAG.

        Args:
            posts: List of BlueskyPost objects or dicts
            existing_analyses: Previously analyzed posts for RAG context

        Returns:
            List of PostAnalysis objects
        """
        # Convert to dicts if needed
        post_dicts = []
        for p in posts:
            if hasattr(p, '__dict__'):
                post_dicts.append(asdict(p) if hasattr(p, 'uri') else p.__dict__)
            else:
                post_dicts.append(p)

        # Get raw analysis with RAG
        raw_results = self.analyze_batch_with_rag(post_dicts, existing_analyses)

        # Build lookup for engagement
        engagement_lookup = {p['uri']: p for p in post_dicts}

        # Convert to PostAnalysis objects
        analyses = []
        for result in raw_results:
            post_data = engagement_lookup.get(result['id'], {})

            # Calculate engagement score (normalized)
            likes = post_data.get('likes', 0)
            reposts = post_data.get('reposts', 0)
            replies = post_data.get('replies', 0)
            engagement = likes + (reposts * 2) + (replies * 1.5)

            analyses.append(PostAnalysis(
                uri=result['id'],
                text=result.get('text', post_data.get('text', '')),
                sentiment=result.get('sentiment', 'neutral_informative'),
                sentiment_confidence=result.get('sentiment_confidence', 0.5),
                topics=result.get('topics', ['General AI Discussion']),
                miri_theses=result.get('miri_theses', []),
                miri_thesis_alignment=result.get('thesis_stance', 'unrelated'),
                engagement_score=engagement,
                summary=result.get('summary', ''),
                embedding=result.get('embedding', []),
                raw_analysis=result
            ))

        return analyses


def analyze_posts_file(
    posts_file: str,
    output_file: str,
    api_key: Optional[str] = None,
    batch_size: int = 10
) -> list[dict]:
    """
    Analyze posts from a JSON file with RAG enhancement.

    Features:
    - Resume capability: skips already-analyzed posts
    - Incremental saving: saves after each batch
    - Detailed logging with progress

    Args:
        posts_file: Path to posts JSON
        output_file: Where to save analysis (also used for resume)
        api_key: Google AI API key
        batch_size: Posts per batch

    Returns:
        List of analysis dicts
    """
    start_time = datetime.now()
    logger.info(f"Starting analysis at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Load posts
    with open(posts_file, 'r', encoding='utf-8') as f:
        all_posts = json.load(f)
    logger.info(f"Loaded {len(all_posts)} posts from {posts_file}")

    # Load existing analyses (for resume + RAG)
    existing_results = []
    analyzed_uris = set()
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_results = json.load(f)
            analyzed_uris = {r.get('uri') or r.get('id') for r in existing_results}
            logger.info(f"Resuming: found {len(existing_results)} already analyzed posts")
        except Exception as e:
            logger.warning(f"Could not load existing results: {e}")

    # Filter to only unanalyzed posts
    posts_to_analyze = [p for p in all_posts if p['uri'] not in analyzed_uris]
    logger.info(f"Posts to analyze: {len(posts_to_analyze)} (skipping {len(analyzed_uris)} already done)")

    if not posts_to_analyze:
        logger.info("All posts already analyzed!")
        return existing_results

    # Initialize analyzer
    analyzer = GeminiAnalyzer(api_key)
    total_batches = (len(posts_to_analyze) - 1) // batch_size + 1

    def get_existing_topics_sorted(results: list[dict]) -> list[str]:
        """Extract topics from results, sorted by frequency (most common first)."""
        topic_counts = {}
        for r in results:
            for topic in r.get('topics', []):
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        # Sort by count descending
        return [t for t, _ in sorted(topic_counts.items(), key=lambda x: -x[1])]

    # Process in batches with incremental saving
    for batch_idx in range(0, len(posts_to_analyze), batch_size):
        batch_num = batch_idx // batch_size + 1
        batch = posts_to_analyze[batch_idx:batch_idx + batch_size]
        batch_start = time.time()

        logger.info(f"=== Batch {batch_num}/{total_batches} ({len(batch)} posts) ===")

        # Get existing topics sorted by frequency (for consistency)
        existing_topics = get_existing_topics_sorted(existing_results)
        if existing_topics:
            logger.info(f"  {len(existing_topics)} existing topics to reuse")

        # Find similar examples for RAG
        similar_examples = []
        if existing_results:
            logger.info("  Finding similar posts for RAG context...")
            for post in batch[:3]:  # Only check first 3 to save time
                similar = analyzer.find_similar_posts(post['text'], existing_results, top_k=10)
                for s in similar:
                    if s not in similar_examples:
                        similar_examples.append(s)
            similar_examples = similar_examples[:15]  # More examples for better RAG
            logger.info(f"  Found {len(similar_examples)} RAG examples")

        # Build prompt and call Gemini
        logger.info("  Calling Gemini API...")
        prompt = analyzer._build_analysis_prompt(batch, similar_examples, existing_topics)

        try:
            response = analyzer.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=4096
                )
            )

            # Parse JSON
            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]

            batch_results = json.loads(text)
            logger.info(f"  Parsed {len(batch_results)} results from Gemini")

            # Generate embeddings
            logger.info("  Generating embeddings...")
            batch_texts = [p['text'] for p in batch]
            embeddings = analyzer.embed_texts(batch_texts)

            # Add embeddings and text to results
            for j, result in enumerate(batch_results):
                result['embedding'] = embeddings[j] if j < len(embeddings) else []
                result['text'] = batch[j]['text'] if j < len(batch) else ''
                # Normalize ID field
                if 'id' in result and 'uri' not in result:
                    result['uri'] = result.pop('id')

            # Add to existing results
            existing_results.extend(batch_results)

            # INCREMENTAL SAVE after each batch
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(existing_results, f, indent=2, ensure_ascii=False)

            batch_time = time.time() - batch_start
            total_done = len(existing_results)
            logger.info(f"  Batch complete in {batch_time:.1f}s | Total: {total_done}/{len(all_posts)} | Saved to {output_file}")

        except json.JSONDecodeError as e:
            logger.error(f"  JSON parse error: {e}")
            logger.error(f"  Raw response: {response.text[:300]}...")
            # Create fallback results
            for post in batch:
                existing_results.append({
                    "uri": post["uri"],
                    "text": post["text"],
                    "sentiment": "neutral_informative",
                    "sentiment_confidence": 0.5,
                    "topics": ["General AI Discussion"],
                    "miri_theses": [],
                    "miri_thesis_alignment": "unrelated",
                    "summary": "Analysis failed - will retry",
                    "embedding": []
                })
            # Still save progress
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(existing_results, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"  Error: {e}")
            logger.info("  Waiting 10s before retry...")
            time.sleep(10)
            continue

        # Rate limiting between batches
        time.sleep(1)

    # Final summary
    elapsed = datetime.now() - start_time
    logger.info(f"\n{'='*50}")
    logger.info(f"ANALYSIS COMPLETE")
    logger.info(f"Total time: {elapsed}")
    logger.info(f"Total posts analyzed: {len(existing_results)}")
    logger.info(f"{'='*50}")

    # Print summary stats
    _print_summary(existing_results)

    return existing_results


def _print_summary(results: list[dict]):
    """Print analysis summary statistics."""
    if not results:
        return

    # Sentiment distribution
    sentiments = {}
    for r in results:
        s = r.get('sentiment', 'unknown')
        sentiments[s] = sentiments.get(s, 0) + 1

    logger.info("\nSentiment Distribution:")
    for s, count in sorted(sentiments.items(), key=lambda x: -x[1]):
        logger.info(f"  {s}: {count} ({100*count/len(results):.1f}%)")

    # Topic discovery
    topics = {}
    for r in results:
        for topic in r.get('topics', []):
            topics[topic] = topics.get(topic, 0) + 1

    logger.info(f"\nDiscovered {len(topics)} unique topics (top 15):")
    for t, count in sorted(topics.items(), key=lambda x: -x[1])[:15]:
        logger.info(f"  {t}: {count}")

    # MIRI thesis mentions
    thesis_counts = {}
    for r in results:
        for thesis in r.get('miri_theses', []):
            thesis_counts[thesis] = thesis_counts.get(thesis, 0) + 1

    if thesis_counts:
        logger.info("\nMIRI Thesis Mentions:")
        for t, count in sorted(thesis_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {t}: {count}")
    else:
        logger.info("\nNo MIRI thesis mentions detected")


if __name__ == "__main__":
    import sys

    posts_file = sys.argv[1] if len(sys.argv) > 1 else "../data/bluesky_posts.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "../data/analysis_results.json"
    batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    analyze_posts_file(posts_file, output_file, batch_size=batch_size)
