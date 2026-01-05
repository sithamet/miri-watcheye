"""
Parallel Gemini Analyzer
Runs analysis in parallel using bootstrap + worker architecture.

Architecture:
1. BOOTSTRAP: Analyze first N posts sequentially to build topic vocabulary + RAG pool
2. PARALLEL: Run M workers in parallel, each with own output file
3. MERGE: Combine all results into single file

This avoids file conflicts while maintaining topic consistency.
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_worker(worker_id: int, posts_chunk: list, bootstrap_file: str, output_file: str):
    """
    Worker function that analyzes a chunk of posts.
    Uses bootstrap data for RAG context and topic consistency.
    """
    import google.generativeai as genai
    from dotenv import load_dotenv
    from gemini_analyzer import GeminiAnalyzer
    from miri_theses import get_thesis_prompt, get_sentiment_prompt

    load_dotenv()

    logger.info(f"[Worker {worker_id}] Starting with {len(posts_chunk)} posts")

    # Load bootstrap data for RAG
    bootstrap_data = []
    existing_topics = []
    if os.path.exists(bootstrap_file):
        with open(bootstrap_file, 'r') as f:
            bootstrap_data = json.load(f)
        # Extract topics sorted by frequency
        topic_counts = {}
        for r in bootstrap_data:
            for t in r.get('topics', []):
                topic_counts[t] = topic_counts.get(t, 0) + 1
        existing_topics = [t for t, _ in sorted(topic_counts.items(), key=lambda x: -x[1])]
        logger.info(f"[Worker {worker_id}] Loaded {len(bootstrap_data)} bootstrap posts, {len(existing_topics)} topics")

    # Initialize analyzer
    analyzer = GeminiAnalyzer()
    results = []
    batch_size = 10

    for batch_idx in range(0, len(posts_chunk), batch_size):
        batch = posts_chunk[batch_idx:batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        total_batches = (len(posts_chunk) - 1) // batch_size + 1

        logger.info(f"[Worker {worker_id}] Batch {batch_num}/{total_batches}")

        # Find similar examples from bootstrap data
        similar_examples = []
        if bootstrap_data:
            for post in batch[:2]:  # Check first 2 posts
                similar = analyzer.find_similar_posts(post['text'], bootstrap_data, top_k=10)
                for s in similar:
                    if s not in similar_examples:
                        similar_examples.append(s)
            similar_examples = similar_examples[:15]

        # Build prompt
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

            # Generate embeddings
            batch_texts = [p['text'] for p in batch]
            embeddings = analyzer.embed_texts(batch_texts)

            # Add embeddings and text
            for j, result in enumerate(batch_results):
                result['embedding'] = embeddings[j] if j < len(embeddings) else []
                result['text'] = batch[j]['text'] if j < len(batch) else ''
                if 'id' in result and 'uri' not in result:
                    result['uri'] = result.pop('id')

            results.extend(batch_results)

            # Save incrementally
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.info(f"[Worker {worker_id}] Batch {batch_num} complete, {len(results)} total")

        except json.JSONDecodeError as e:
            logger.error(f"[Worker {worker_id}] JSON error: {e}")
            # Fallback results
            for post in batch:
                results.append({
                    "uri": post["uri"],
                    "text": post["text"],
                    "sentiment": "neutral_informative",
                    "sentiment_confidence": 0.5,
                    "topics": ["General AI Discussion"],
                    "miri_theses": [],
                    "miri_thesis_alignment": "unrelated",
                    "summary": "Analysis failed",
                    "embedding": []
                })
        except Exception as e:
            logger.error(f"[Worker {worker_id}] Error: {e}")
            time.sleep(5)

        # Rate limiting
        time.sleep(1)

    logger.info(f"[Worker {worker_id}] Complete! {len(results)} posts analyzed")
    return len(results)


def run_parallel_analysis(
    posts_file: str,
    output_file: str,
    num_workers: int = 5,
    bootstrap_size: int = 100,
    batch_size: int = 10
):
    """
    Run parallel analysis with bootstrap phase.

    Args:
        posts_file: Input posts JSON
        output_file: Final output file
        num_workers: Number of parallel workers
        bootstrap_size: Posts to analyze in bootstrap phase
        batch_size: Posts per Gemini API call
    """
    start_time = datetime.now()
    data_dir = Path(posts_file).parent

    logger.info(f"{'='*60}")
    logger.info(f"PARALLEL ANALYZER - {num_workers} workers")
    logger.info(f"{'='*60}")

    # Load all posts
    with open(posts_file, 'r') as f:
        all_posts = json.load(f)
    logger.info(f"Loaded {len(all_posts)} posts")

    # ========== PHASE 1: BOOTSTRAP ==========
    logger.info(f"\n{'='*60}")
    logger.info(f"PHASE 1: BOOTSTRAP ({bootstrap_size} posts)")
    logger.info(f"{'='*60}")

    bootstrap_file = data_dir / "analysis_bootstrap.json"
    bootstrap_posts_file = data_dir / "bootstrap_posts_temp.json"

    # Create temp file with just bootstrap posts
    bootstrap_posts = all_posts[:bootstrap_size]
    with open(bootstrap_posts_file, 'w') as f:
        json.dump(bootstrap_posts, f)

    # Run bootstrap sequentially using existing analyzer
    from gemini_analyzer import analyze_posts_file
    analyze_posts_file(
        posts_file=str(bootstrap_posts_file),
        output_file=str(bootstrap_file),
        batch_size=batch_size
    )

    # Cleanup temp file
    if bootstrap_posts_file.exists():
        bootstrap_posts_file.unlink()

    # Load bootstrap results (might be fewer if it already existed)
    with open(bootstrap_file, 'r') as f:
        bootstrap_results = json.load(f)

    # Get URIs already analyzed in bootstrap
    bootstrap_uris = {r.get('uri') or r.get('id') for r in bootstrap_results}
    remaining_posts = [p for p in all_posts if p['uri'] not in bootstrap_uris]

    logger.info(f"Bootstrap complete: {len(bootstrap_results)} posts")
    logger.info(f"Remaining for parallel phase: {len(remaining_posts)}")

    if not remaining_posts:
        logger.info("All posts analyzed in bootstrap phase!")
        # Copy bootstrap to final output
        with open(output_file, 'w') as f:
            json.dump(bootstrap_results, f, indent=2, ensure_ascii=False)
        return bootstrap_results

    # ========== PHASE 2: PARALLEL WORKERS ==========
    logger.info(f"\n{'='*60}")
    logger.info(f"PHASE 2: PARALLEL ({num_workers} workers, {len(remaining_posts)} posts)")
    logger.info(f"{'='*60}")

    # Split remaining posts into chunks
    chunk_size = len(remaining_posts) // num_workers + 1
    chunks = []
    for i in range(0, len(remaining_posts), chunk_size):
        chunks.append(remaining_posts[i:i + chunk_size])

    # Create worker output files
    worker_files = [data_dir / f"results_worker_{i}.json" for i in range(len(chunks))]

    logger.info(f"Split into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        logger.info(f"  Worker {i}: {len(chunk)} posts → {worker_files[i].name}")

    # Run workers in parallel using subprocess for true parallelism
    # (ProcessPoolExecutor has issues with genai client)
    processes = []
    for i, (chunk, worker_file) in enumerate(zip(chunks, worker_files)):
        # Save chunk to temp file
        chunk_file = data_dir / f"chunk_{i}.json"
        with open(chunk_file, 'w') as f:
            json.dump(chunk, f)

        # Start worker process
        cmd = [
            sys.executable, "-c",
            f"""
import sys
sys.path.insert(0, '{Path(__file__).parent}')
import json
from parallel_analyzer import run_worker
with open('{chunk_file}', 'r') as f:
    posts = json.load(f)
run_worker({i}, posts, '{bootstrap_file}', '{worker_file}')
"""
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        processes.append((i, proc, chunk_file))
        logger.info(f"Started worker {i} (PID: {proc.pid})")
        time.sleep(2)  # Stagger starts to avoid rate limiting

    # Wait for all workers to complete
    logger.info("\nWaiting for workers to complete...")
    for worker_id, proc, chunk_file in processes:
        proc.wait()
        logger.info(f"Worker {worker_id} finished (exit code: {proc.returncode})")
        # Cleanup chunk file
        if chunk_file.exists():
            chunk_file.unlink()

    # ========== PHASE 3: MERGE ==========
    logger.info(f"\n{'='*60}")
    logger.info(f"PHASE 3: MERGE")
    logger.info(f"{'='*60}")

    # Combine all results
    all_results = bootstrap_results.copy()

    for worker_file in worker_files:
        if worker_file.exists():
            with open(worker_file, 'r') as f:
                worker_results = json.load(f)
            logger.info(f"Loaded {len(worker_results)} from {worker_file.name}")
            all_results.extend(worker_results)
            # Cleanup worker file
            worker_file.unlink()

    # Deduplicate by URI (shouldn't happen but just in case)
    seen_uris = set()
    deduped_results = []
    for r in all_results:
        uri = r.get('uri') or r.get('id')
        if uri not in seen_uris:
            seen_uris.add(uri)
            deduped_results.append(r)

    # Save final results
    with open(output_file, 'w') as f:
        json.dump(deduped_results, f, indent=2, ensure_ascii=False)

    elapsed = datetime.now() - start_time

    logger.info(f"\n{'='*60}")
    logger.info(f"COMPLETE!")
    logger.info(f"Total posts analyzed: {len(deduped_results)}")
    logger.info(f"Total time: {elapsed}")
    logger.info(f"Output: {output_file}")
    logger.info(f"{'='*60}")

    # Print topic stats
    topics = {}
    for r in deduped_results:
        for t in r.get('topics', []):
            topics[t] = topics.get(t, 0) + 1
    logger.info(f"\n{len(topics)} unique topics discovered")
    logger.info("Top 15 topics:")
    for t, c in sorted(topics.items(), key=lambda x: -x[1])[:15]:
        logger.info(f"  {c:4d}: {t}")

    return deduped_results


if __name__ == "__main__":
    posts_file = sys.argv[1] if len(sys.argv) > 1 else "../data/bluesky_posts.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "../data/analysis_results.json"
    num_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    bootstrap_size = int(sys.argv[4]) if len(sys.argv) > 4 else 100

    run_parallel_analysis(
        posts_file=posts_file,
        output_file=output_file,
        num_workers=num_workers,
        bootstrap_size=bootstrap_size
    )
