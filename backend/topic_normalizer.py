"""
Topic Normalization - Two-pass approach
Pass 2: Create taxonomy from discovered topics
Pass 3: Apply mapping to all posts
"""

import json
import logging
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def extract_all_topics(results: list[dict]) -> dict[str, int]:
    """Extract all topics with counts from analysis results."""
    topics = {}
    for r in results:
        for t in r.get('topics', []):
            topics[t] = topics.get(t, 0) + 1
    return topics


def create_taxonomy_prompt(topics: dict[str, int], target_count: int = 30) -> str:
    """Build prompt for taxonomy creation."""
    topics_list = "\n".join([
        f"- {topic} ({count}x)"
        for topic, count in sorted(topics.items(), key=lambda x: -x[1])
    ])

    return f"""You are creating a topic taxonomy for AI discourse analysis.

Here are {len(topics)} topics discovered from social media posts about AI, with frequency counts:

{topics_list}

Your task:
1. Create exactly {target_count} canonical topic categories that cover ALL these topics
2. Map EVERY original topic to exactly one canonical topic
3. Canonical topics should be meaningful groupings, not too broad or narrow

Rules:
- Every original topic MUST appear in the mapping
- Canonical topic IDs should be snake_case (e.g., "ai_employment", "chatgpt_product")
- "Not AI Related" should map to "not_ai_related"

Return ONLY valid JSON (no markdown):
{{
  "canonical_topics": [
    {{"id": "snake_case_id", "name": "Human Readable Name", "description": "Brief description"}},
    ...
  ],
  "mapping": {{
    "Original Topic 1": "canonical_id",
    "Original Topic 2": "canonical_id",
    ...
  }}
}}"""


def create_taxonomy(
    topics: dict[str, int],
    target_count: int = 30,
    api_key: Optional[str] = None
) -> dict:
    """
    Pass 2: Create taxonomy from discovered topics.
    Returns canonical topics and mapping.
    """
    import os
    import re
    api_key = api_key or os.getenv('GOOGLE_API_KEY')
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    prompt = create_taxonomy_prompt(topics, target_count)

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Creating taxonomy (attempt {attempt + 1}/{MAX_RETRIES})...")

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=65536,
                    response_mime_type="application/json"
                )
            )

            # Parse JSON
            text = response.text.strip()

            # Clean up any markdown code blocks
            if '```' in text:
                # Extract content between code blocks
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
                if match:
                    text = match.group(1)
                else:
                    # Just remove the backticks
                    text = text.replace('```json', '').replace('```', '')

            text = text.strip()

            taxonomy = json.loads(text)

            # Validate
            if not validate_taxonomy(taxonomy, topics):
                raise ValueError("Taxonomy validation failed")

            logger.info(f"Created {len(taxonomy['canonical_topics'])} canonical topics")
            return taxonomy

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            if attempt == MAX_RETRIES - 1:
                raise
        except Exception as e:
            logger.error(f"Error: {e}")
            if attempt == MAX_RETRIES - 1:
                raise

    raise RuntimeError("Failed to create taxonomy after retries")


def validate_taxonomy(taxonomy: dict, original_topics: dict[str, int]) -> bool:
    """Validate taxonomy completeness and structure."""
    errors = []

    # Check structure
    if 'canonical_topics' not in taxonomy:
        errors.append("Missing 'canonical_topics'")
    if 'mapping' not in taxonomy:
        errors.append("Missing 'mapping'")

    if errors:
        logger.error(f"Validation errors: {errors}")
        return False

    # Check all original topics are mapped
    mapping = taxonomy['mapping']
    canonical_ids = {t['id'] for t in taxonomy['canonical_topics']}

    for topic in original_topics:
        if topic not in mapping:
            errors.append(f"Topic not mapped: {topic}")
        elif mapping[topic] not in canonical_ids:
            errors.append(f"Invalid canonical ID for '{topic}': {mapping[topic]}")

    if errors:
        logger.error(f"Validation errors ({len(errors)}): {errors[:5]}...")
        return False

    logger.info("Taxonomy validation passed")
    return True


def apply_mapping(results: list[dict], taxonomy: dict) -> list[dict]:
    """
    Pass 3: Apply mapping to normalize topics.
    Adds 'topics_normalized' field to each result.
    """
    mapping = taxonomy['mapping']
    canonical_lookup = {t['id']: t['name'] for t in taxonomy['canonical_topics']}

    updated = 0
    unmapped_topics = set()
    for result in results:
        raw_topics = result.get('topics', [])
        normalized = []

        for topic in raw_topics:
            if topic in mapping:
                canonical_id = mapping[topic]
                normalized.append(canonical_id)
            else:
                # Unmapped topic - keep as-is but track
                unmapped_topics.add(topic)
                normalized.append(topic.lower().replace(' ', '_'))

        # Dedupe while preserving order
        seen = set()
        result['topics_normalized'] = [
            t for t in normalized
            if not (t in seen or seen.add(t))
        ]
        result['topics_raw'] = raw_topics
        updated += 1

    if unmapped_topics:
        logger.warning(f"Unmapped topics ({len(unmapped_topics)}): {list(unmapped_topics)[:10]}...")

    logger.info(f"Applied mapping to {updated} posts")
    return results


def normalize_topics(
    input_file: str,
    output_file: str,
    taxonomy_file: str,
    target_topics: int = 30
):
    """
    Main function: Run Pass 2 + Pass 3.
    """
    logger.info("=" * 60)
    logger.info("TOPIC NORMALIZATION")
    logger.info("=" * 60)

    # Load results
    with open(input_file, 'r') as f:
        results = json.load(f)
    logger.info(f"Loaded {len(results)} posts from {input_file}")

    # Extract topics
    topics = extract_all_topics(results)
    logger.info(f"Found {len(topics)} unique topics")

    # Pass 2: Create taxonomy
    taxonomy = create_taxonomy(topics, target_topics)

    # Save taxonomy
    with open(taxonomy_file, 'w') as f:
        json.dump(taxonomy, f, indent=2)
    logger.info(f"Saved taxonomy to {taxonomy_file}")

    # Pass 3: Apply mapping
    results = apply_mapping(results, taxonomy)

    # Save updated results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved normalized results to {output_file}")

    # Print summary
    print_summary(results, taxonomy)

    return results, taxonomy


def print_summary(results: list[dict], taxonomy: dict):
    """Print normalization summary."""
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    # Count normalized topics
    norm_counts = {}
    for r in results:
        for t in r.get('topics_normalized', []):
            norm_counts[t] = norm_counts.get(t, 0) + 1

    canonical_lookup = {t['id']: t['name'] for t in taxonomy['canonical_topics']}

    logger.info(f"\n{len(taxonomy['canonical_topics'])} Canonical Topics:")
    for tid, count in sorted(norm_counts.items(), key=lambda x: -x[1])[:20]:
        name = canonical_lookup.get(tid, tid)
        logger.info(f"  {count:4d}: {name} ({tid})")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

    input_file = sys.argv[1] if len(sys.argv) > 1 else "../data/analysis_results.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "../data/analysis_normalized.json"
    taxonomy_file = sys.argv[3] if len(sys.argv) > 3 else "../data/topic_taxonomy.json"

    normalize_topics(input_file, output_file, taxonomy_file)
