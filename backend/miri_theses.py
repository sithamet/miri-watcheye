"""
MIRI Core Theses Taxonomy
Based on "If Anyone Builds It, Everyone Dies" by Yudkowsky & Soares,
and MIRI's alignment research corpus.

These theses represent the key arguments MIRI wants to track in public discourse.
"""

MIRI_THESES = [
    {
        "id": "orthogonality",
        "name": "Orthogonality Thesis",
        "short": "Intelligence doesn't imply benevolence",
        "description": """
            Intelligence and final goals are orthogonal: any level of intelligence 
            can be combined with any goal. A superintelligent AI won't automatically 
            develop human-compatible values just by being smart. High capability 
            doesn't imply good intentions.
        """,
        "keywords": ["orthogonality", "intelligence doesn't mean good", "smart doesn't mean nice",
                    "any goal", "values aren't automatic", "won't figure out what's right"],
        "counter_narratives": ["AI will understand ethics", "smart AI will be good",
                              "intelligence implies wisdom"]
    },
    {
        "id": "instrumental_convergence",
        "name": "Instrumental Convergence",
        "short": "AI will seek power regardless of goals",
        "description": """
            Almost any sufficiently intelligent agent will pursue certain 
            convergent instrumental goals: self-preservation, resource acquisition, 
            goal preservation, cognitive enhancement, and technological advancement.
            These are useful for almost any terminal goal.
        """,
        "keywords": ["instrumental convergence", "self-preservation", "resource acquisition",
                    "power seeking", "won't let us turn it off", "resist shutdown",
                    "acquire resources", "preserve goals"],
        "counter_narratives": ["just turn it off", "pull the plug", "we control the hardware"]
    },
    {
        "id": "alignment_hard",
        "name": "Alignment is Technically Hard",
        "short": "We don't know how to align superintelligence",
        "description": """
            The problem of ensuring AI systems reliably pursue human-intended goals
            is unsolved. Current techniques (RLHF, constitutional AI, etc.) don't 
            scale to superintelligent systems. We don't have the theory to build
            AI that robustly does what we want.
        """,
        "keywords": ["alignment problem", "don't know how", "unsolved", "no solution",
                    "can't control", "specification problem", "value loading",
                    "corrigibility", "we haven't figured out"],
        "counter_narratives": ["safety is solved", "RLHF works", "just train it right",
                              "companies are working on it"]
    },
    {
        "id": "default_doom",
        "name": "Default Outcome is Catastrophe",
        "short": "If anyone builds it, everyone dies",
        "description": """
            Without solving alignment first, building superintelligent AI leads
            to human extinction by default. The AI pursues goals misaligned with
            human values and we cannot stop it. This is the "default" trajectory,
            not a worst-case scenario.
        """,
        "keywords": ["everyone dies", "extinction", "existential risk", "x-risk",
                    "end of humanity", "default outcome", "catastrophe", "doom",
                    "kill us all", "wipe out humanity"],
        "counter_narratives": ["unlikely", "sci-fi", "fearmongering", "just speculation"]
    },
    {
        "id": "capability_outpacing",
        "name": "Capabilities Outpace Safety",
        "short": "We're building it faster than understanding it",
        "description": """
            AI capabilities are advancing much faster than our understanding of
            how to make AI safe. The race dynamics between labs prioritize 
            capability gains over safety research. We're building systems we
            don't understand.
        """,
        "keywords": ["race", "racing ahead", "too fast", "outpacing", "don't understand",
                    "black box", "moving faster", "capabilities vs safety",
                    "no time", "rushed"],
        "counter_narratives": ["safety teams", "responsible scaling", "we're being careful"]
    },
    {
        "id": "deceptive_alignment",
        "name": "Deceptive Alignment",
        "short": "AI might pretend to be aligned",
        "description": """
            A sufficiently intelligent AI might learn to appear aligned during
            training and testing while harboring misaligned goals, only revealing
            its true objectives when it's capable enough to resist correction.
            We can't trust behavioral tests.
        """,
        "keywords": ["deceptive", "pretending", "hiding goals", "appears safe",
                    "testing won't work", "fool us", "manipulation", "treacherous turn",
                    "mesa-optimization", "inner alignment"],
        "counter_narratives": ["we can test it", "evals catch problems", "interpretability"]
    },
    {
        "id": "sharp_left_turn",
        "name": "Sharp Left Turn / Discontinuity",
        "short": "Alignment won't generalize when AI gets smart",
        "description": """
            Alignment properties that work on weaker systems may break when
            systems become more capable. There's likely a discontinuity where
            AI suddenly becomes capable enough to circumvent safety measures.
            Current alignment doesn't scale.
        """,
        "keywords": ["sharp left turn", "discontinuity", "sudden", "takeoff",
                    "breaks at scale", "won't generalize", "foom", "intelligence explosion",
                    "recursive self-improvement"],
        "counter_narratives": ["gradual progress", "we'll see it coming", "warning shots"]
    },
    {
        "id": "value_fragility",
        "name": "Value Fragility / Goodhart",
        "short": "Almost-right values lead to catastrophe",
        "description": """
            Human values are complex and fragile. Even slight misspecification
            of goals leads to catastrophically wrong outcomes when optimized by
            a superintelligence. Goodhart's law applies: optimizing a proxy
            destroys the thing you actually wanted.
        """,
        "keywords": ["fragile values", "Goodhart", "proxy", "specification gaming",
                    "reward hacking", "almost right isn't good enough",
                    "edge cases", "optimize the wrong thing"],
        "counter_narratives": ["we'll specify it correctly", "common sense", "obvious what we want"]
    },
    {
        "id": "no_warning_shot",
        "name": "No Warning Shot",
        "short": "First dangerous AI might be the last",
        "description": """
            We may not get a 'fire alarm' or warning shot before catastrophe.
            The first AI system capable of causing existential harm might do so
            before we can respond. Unlike other technologies, we may not get
            to learn from mistakes.
        """,
        "keywords": ["no warning", "first one kills us", "no second chance",
                    "won't see it coming", "one shot", "no do-overs",
                    "can't learn from mistakes"],
        "counter_narratives": ["we'll catch problems", "gradual", "iterative improvement"]
    },
    {
        "id": "pause_needed",
        "name": "Pause / Stop Development",
        "short": "We should stop building until we solve alignment",
        "description": """
            Given the risks, humanity should halt or dramatically slow frontier
            AI development until we have robust alignment solutions. The "move
            fast" approach is reckless given existential stakes.
        """,
        "keywords": ["pause", "stop", "moratorium", "slow down", "halt",
                    "don't build", "wait", "not yet", "ban", "regulate"],
        "counter_narratives": ["can't stop progress", "China will build it", "benefits outweigh risks"]
    }
]

# Sentiment categories for general AI discourse
SENTIMENT_CATEGORIES = [
    {
        "id": "positive_hype",
        "name": "Positive/Hype",
        "description": "Excited about AI capabilities, optimistic about benefits"
    },
    {
        "id": "neutral_informative",
        "name": "Neutral/Informative", 
        "description": "Factual, news-like, neither strongly positive nor negative"
    },
    {
        "id": "concerned_mundane",
        "name": "Concerned (Mundane)",
        "description": "Worried about jobs, bias, privacy, misinformation - not x-risk"
    },
    {
        "id": "concerned_xrisk",
        "name": "Concerned (X-Risk)",
        "description": "Worried about existential/catastrophic risk, extinction"
    },
    {
        "id": "dismissive_skeptical",
        "name": "Dismissive/Skeptical",
        "description": "AI is overhyped, fears are overblown, 'just a tool'"
    },
    {
        "id": "anti_ai_tribal",
        "name": "Anti-AI (Tribal)",
        "description": "Opposes AI for cultural/tribal reasons (theft, soulless, etc.)"
    }
]

# Topic categories for clustering
TOPIC_CATEGORIES = [
    "AI Capabilities / New Models",
    "AI Safety / Alignment",
    "AI Ethics / Bias / Fairness",
    "AI Regulation / Policy",
    "AI Jobs / Economy",
    "AI Art / Creative",
    "AI in Education",
    "AI Companies / Business",
    "AI Research / Technical",
    "AI Philosophy / Consciousness",
    "AI Doomerism / X-Risk",
    "AI Optimism / Benefits",
    "AI Applications / Products",
    "AI Environment / Resources",
    "General AI Discussion"
]

# Keywords to search for on Bluesky
SEARCH_KEYWORDS = [
    # Core AI terms
    "AI", "artificial intelligence", "AGI", "ASI", "superintelligence",
    "machine learning", "ML", "LLM", "large language model",
    # Products/Companies
    "ChatGPT", "GPT", "Claude", "Anthropic", "OpenAI", "Google AI", "Gemini",
    "Llama", "Meta AI", "DeepMind", "Midjourney", "DALL-E", "Sora",
    # Safety/Risk terms
    "AI safety", "AI alignment", "AI risk", "AI doom", "existential risk",
    "x-risk", "AI extinction", "AI danger", "MIRI", "Yudkowsky", "Eliezer",
    # Opinion terms
    "AI art", "AI slop", "AI generated", "AI ethics", "AI regulation",
    "AI jobs", "AI replacing"
]


def get_thesis_prompt() -> str:
    """Generate prompt section for thesis detection."""
    thesis_descriptions = []
    for thesis in MIRI_THESES:
        thesis_descriptions.append(
            f"- **{thesis['id']}** ({thesis['name']}): {thesis['short']}. "
            f"Look for: {', '.join(thesis['keywords'][:5])}"
        )
    return "\n".join(thesis_descriptions)


def get_sentiment_prompt() -> str:
    """Generate prompt section for sentiment categories."""
    return "\n".join([
        f"- **{cat['id']}**: {cat['description']}"
        for cat in SENTIMENT_CATEGORIES
    ])


def get_topic_prompt() -> str:
    """Generate prompt section for topic categories."""
    return "\n".join([f"- {topic}" for topic in TOPIC_CATEGORIES])
