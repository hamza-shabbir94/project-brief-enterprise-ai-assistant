"""
All project settings in one place.

Change values here instead of hunting through the code.
"""

from pathlib import Path

# --- Paths ---------------------------------------------------------------
PROJECT_DIR = Path(__file__).parent
DOCUMENTS_DIR = PROJECT_DIR / "documents"    # where the PDFs live

# --- Vector store --------------------------------------------------------
# "pinecone": hosted in the cloud, works the same locally and when deployed.
# "chroma":   saved in a local folder, no account needed, good for offline experiments.
VECTOR_STORE = "pinecone"

PINECONE_INDEX_NAME = "ironstore-assistant"
PINECONE_CLOUD = "aws"                       # the free plan only offers aws / us-east-1
PINECONE_REGION = "us-east-1"

CHROMA_DIR = PROJECT_DIR / "chroma_db"
COLLECTION_NAME = "ironstore_docs"

# --- OpenAI models -------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-small"   # turns text into vectors (cheap)
EMBEDDING_DIMENSIONS = 1536                  # length of each vector for this model
CHAT_MODEL = "gpt-4o-mini"                   # writes the answers
TEMPERATURE = 0                              # 0 = factual, no creativity

# --- Chunking ------------------------------------------------------------
# A product entry in the catalogs is ~600-900 characters, so 1200 keeps
# most products in one piece. The overlap repeats a bit of text between
# neighbouring chunks so nothing gets lost at the boundary.
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

# --- Retrieval -----------------------------------------------------------
TOP_K = 6                                    # how many chunks to give the LLM

# Chunks less similar than this (cosine similarity, 0-1) are dropped. In this
# data, related chunks score ~0.45-0.65 and off-topic questions ("What is the
# capital of France?") ~0.2. If nothing passes, the assistant says it couldn't
# find the answer instead of letting the LLM guess from unrelated text.
# Run `python -m evaluation.evaluate` after changing it.
MIN_RELEVANCE = 0.30

# --- Conversation memory -------------------------------------------------
# How many previous messages (questions + answers) are used to understand
# follow-up questions like "and for contractors?".
HISTORY_MESSAGES = 6

# --- Evaluation ----------------------------------------------------------
# A stronger model grades the assistant's answers (LLM-as-a-judge).
JUDGE_MODEL = "gpt-4o"

# --- Data quality --------------------------------------------------------
# Documents last reviewed before this year are treated as outdated and
# left out of answers (e.g. the 2021 product catalog).
OUTDATED_BEFORE_YEAR = 2025
