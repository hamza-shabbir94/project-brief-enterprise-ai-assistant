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

# --- Data quality --------------------------------------------------------
# Documents last reviewed before this year are treated as outdated and
# left out of answers (e.g. the 2021 product catalog).
OUTDATED_BEFORE_YEAR = 2025
