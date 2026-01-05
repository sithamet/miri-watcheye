"""
Bluesky Data Fetcher
Uses AT Protocol to fetch posts matching AI-related keywords.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, asdict
from atproto import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class BlueskyPost:
    """Represents a Bluesky post with relevant metadata."""
    uri: str
    cid: str
    author_handle: str
    author_display_name: str
    author_did: str
    text: str
    created_at: str
    likes: int
    reposts: int
    replies: int
    web_url: str
    is_reply: bool
    reply_parent_uri: Optional[str] = None
    reply_root_uri: Optional[str] = None
    

class BlueskyFetcher:
    """Fetches posts from Bluesky using AT Protocol."""
    
    def __init__(self, handle: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            handle: Bluesky handle (e.g., 'user.bsky.social')
            password: App password (not main password)
        """
        self.client = Client()
        self.handle = handle or os.getenv('BLUESKY_HANDLE')
        self.password = password or os.getenv('BLUESKY_PASSWORD')
        self.logged_in = False
        
    def login(self) -> bool:
        """Authenticate with Bluesky."""
        if not self.handle or not self.password:
            print("Warning: No credentials provided. Using unauthenticated access (limited).")
            return False
        
        try:
            self.client.login(self.handle, self.password)
            self.logged_in = True
            print(f"Logged in as {self.handle}")
            return True
        except Exception as e:
            print(f"Login failed: {e}")
            return False
    
    def _post_to_dataclass(self, post) -> BlueskyPost:
        """Convert API post object to our dataclass."""
        record = post.record if hasattr(post, 'record') else post
        author = post.author
        
        # Build web URL
        handle = author.handle
        # Extract record key from URI
        uri_parts = post.uri.split('/')
        record_key = uri_parts[-1] if uri_parts else ''
        web_url = f"https://bsky.app/profile/{handle}/post/{record_key}"
        
        # Check if reply
        is_reply = hasattr(record, 'reply') and record.reply is not None
        reply_parent = None
        reply_root = None
        if is_reply:
            reply_parent = record.reply.parent.uri if hasattr(record.reply, 'parent') else None
            reply_root = record.reply.root.uri if hasattr(record.reply, 'root') else None
        
        return BlueskyPost(
            uri=post.uri,
            cid=post.cid,
            author_handle=author.handle,
            author_display_name=author.display_name or author.handle,
            author_did=author.did,
            text=record.text if hasattr(record, 'text') else '',
            created_at=record.created_at if hasattr(record, 'created_at') else '',
            likes=post.like_count if hasattr(post, 'like_count') else 0,
            reposts=post.repost_count if hasattr(post, 'repost_count') else 0,
            replies=post.reply_count if hasattr(post, 'reply_count') else 0,
            web_url=web_url,
            is_reply=is_reply,
            reply_parent_uri=reply_parent,
            reply_root_uri=reply_root
        )
    
    def search_posts(
        self,
        query: str,
        limit: int = 100,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        lang: str = "en"
    ) -> list[BlueskyPost]:
        """
        Search for posts matching a query.
        
        Args:
            query: Search query string
            limit: Maximum number of posts to fetch
            since: Only posts after this datetime
            until: Only posts before this datetime
            lang: Language filter (default 'en')
            
        Returns:
            List of BlueskyPost objects
        """
        posts = []
        cursor = None
        fetched = 0
        
        # Build params
        params = {
            'q': query,
            'limit': min(100, limit),  # API max is 100 per request
            'lang': lang
        }
        
        if since:
            params['since'] = since.isoformat() + 'Z'
        if until:
            params['until'] = until.isoformat() + 'Z'
        
        print(f"Searching for: '{query}'")
        
        while fetched < limit:
            try:
                if cursor:
                    params['cursor'] = cursor
                
                response = self.client.app.bsky.feed.search_posts(params=params)
                
                if not response.posts:
                    break
                
                for post in response.posts:
                    if fetched >= limit:
                        break
                    try:
                        posts.append(self._post_to_dataclass(post))
                        fetched += 1
                    except Exception as e:
                        print(f"Error processing post: {e}")
                        continue
                
                cursor = response.cursor
                if not cursor:
                    break
                    
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error fetching posts: {e}")
                break
        
        print(f"Fetched {len(posts)} posts for query '{query}'")
        return posts
    
    def fetch_for_keywords(
        self,
        keywords: list[str],
        posts_per_keyword: int = 50,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> list[BlueskyPost]:
        """
        Fetch posts for multiple keywords.
        
        Args:
            keywords: List of search terms
            posts_per_keyword: Max posts per keyword
            since: Only posts after this datetime
            until: Only posts before this datetime
            
        Returns:
            Deduplicated list of posts
        """
        all_posts = {}  # uri -> post for deduplication
        
        for keyword in keywords:
            posts = self.search_posts(
                query=keyword,
                limit=posts_per_keyword,
                since=since,
                until=until
            )
            for post in posts:
                if post.uri not in all_posts:
                    all_posts[post.uri] = post
            
            # Rate limiting between keywords
            time.sleep(1)
        
        result = list(all_posts.values())
        print(f"\nTotal unique posts: {len(result)}")
        return result
    
    def save_posts(self, posts: list[BlueskyPost], filepath: str):
        """Save posts to JSON file."""
        data = [asdict(p) for p in posts]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(posts)} posts to {filepath}")
    
    def load_posts(self, filepath: str) -> list[BlueskyPost]:
        """Load posts from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [BlueskyPost(**p) for p in data]


def fetch_recent_ai_posts(
    handle: Optional[str] = None,
    password: Optional[str] = None,
    days_back: int = 7,
    output_file: str = "bluesky_posts.json",
    posts_per_keyword: int = 100,
    max_total_posts: int = 1000
) -> list[BlueskyPost]:
    """
    Fetch recent AI-related posts, sorted by engagement.

    Args:
        handle: Bluesky handle
        password: App password
        days_back: Number of days to look back (default 7)
        output_file: Where to save results
        posts_per_keyword: Max posts per keyword (default 100)
        max_total_posts: Keep only top N posts by engagement (default 1000)

    Returns:
        List of posts sorted by engagement
    """
    fetcher = BlueskyFetcher(handle, password)
    fetcher.login()

    until = datetime.utcnow()
    since = until - timedelta(days=days_back)

    print(f"Fetching posts from {since.date()} to {until.date()} ({days_back} days)")

    # BROAD keyword list per spec - include generic terms!
    keywords = [
        # Generic high-volume terms (CRITICAL for coverage)
        "AI", "GenAI", "artificial intelligence",
        "machine learning", "LLM", "large language model",
        # Products/Companies
        "ChatGPT", "GPT-4", "GPT-5", "OpenAI",
        "Claude", "Anthropic",
        "Gemini", "Google AI", "DeepMind",
        "Llama", "Meta AI",
        "Midjourney", "DALL-E", "Sora",
        # Safety/Risk terms
        "AI safety", "AI alignment", "AI risk", "AI doom",
        "existential risk", "x-risk", "superintelligence", "AGI",
        "MIRI", "Yudkowsky",
        # Opinion/hot topics
        "AI art", "AI slop", "AI generated",
        "AI ethics", "AI regulation", "AI bias",
        "AI jobs", "AI replacing",
    ]

    print(f"Using {len(keywords)} keywords, up to {posts_per_keyword} posts each")

    posts = fetcher.fetch_for_keywords(
        keywords=keywords,
        posts_per_keyword=posts_per_keyword,
        since=since,
        until=until
    )

    print(f"\nTotal fetched (before filtering): {len(posts)}")

    # Sort by engagement and keep top N
    if len(posts) > max_total_posts:
        print(f"Filtering to top {max_total_posts} by engagement...")
        # Engagement score: likes + reposts*2 + replies*1.5
        posts.sort(
            key=lambda p: p.likes + (p.reposts * 2) + (p.replies * 1.5),
            reverse=True
        )
        posts = posts[:max_total_posts]
        print(f"Kept top {len(posts)} posts")

    # Show engagement stats
    if posts:
        avg_likes = sum(p.likes for p in posts) / len(posts)
        avg_reposts = sum(p.reposts for p in posts) / len(posts)
        print(f"Avg engagement: {avg_likes:.1f} likes, {avg_reposts:.1f} reposts")

    fetcher.save_posts(posts, output_file)
    return posts


if __name__ == "__main__":
    # Test run
    import sys
    
    handle = sys.argv[1] if len(sys.argv) > 1 else None
    password = sys.argv[2] if len(sys.argv) > 2 else None
    
    posts = fetch_recent_ai_posts(handle, password)
    print(f"\nSample post:")
    if posts:
        p = posts[0]
        print(f"  Author: {p.author_display_name} (@{p.author_handle})")
        print(f"  Text: {p.text[:200]}...")
        print(f"  Engagement: {p.likes} likes, {p.reposts} reposts, {p.replies} replies")
