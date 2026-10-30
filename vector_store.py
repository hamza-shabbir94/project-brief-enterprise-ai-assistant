"""
Where the chunks and their embeddings are stored.

Both ingest.py (writes) and rag.py (reads) get the vector store from here,
so switching between Pinecone and Chroma is one line in config.py.
"""

import shutil

from langchain_openai import OpenAIEmbeddings

import config


def get_embeddings():
    return OpenAIEmbeddings(model=config.EMBEDDING_MODEL)


def get_vector_store():
    """Connect to the existing vector store (used when answering questions)."""
    if config.VECTOR_STORE == "pinecone":
        from langchain_pinecone import PineconeVectorStore
        from pinecone import Pinecone

        if not Pinecone().has_index(config.PINECONE_INDEX_NAME):
            raise RuntimeError("No Pinecone index found. Run `python ingest.py` first.")
        return PineconeVectorStore(index_name=config.PINECONE_INDEX_NAME, embedding=get_embeddings())

    if config.VECTOR_STORE == "chroma":
        from langchain_chroma import Chroma

        if not config.CHROMA_DIR.exists():
            raise FileNotFoundError("No vector store found. Run `python ingest.py` first.")
        return Chroma(
            collection_name=config.COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=str(config.CHROMA_DIR),
        )

    raise ValueError(f"Unknown VECTOR_STORE in config.py: {config.VECTOR_STORE!r}")


def create_empty_vector_store():
    """Delete any old data and return an empty store (used by ingest.py).

    Starting from empty means re-running ingest.py doesn't store everything twice.
    """
    if config.VECTOR_STORE == "pinecone":
        from pinecone import Pinecone, ServerlessSpec

        pc = Pinecone()  # reads PINECONE_API_KEY from the environment
        if pc.has_index(config.PINECONE_INDEX_NAME):
            pc.delete_index(config.PINECONE_INDEX_NAME)
        pc.create_index(
            name=config.PINECONE_INDEX_NAME,
            dimension=config.EMBEDDING_DIMENSIONS,  # must match the embedding model
            metric="cosine",
            spec=ServerlessSpec(cloud=config.PINECONE_CLOUD, region=config.PINECONE_REGION),
        )

    elif config.VECTOR_STORE == "chroma":
        if config.CHROMA_DIR.exists():
            shutil.rmtree(config.CHROMA_DIR)
        config.CHROMA_DIR.mkdir()

    return get_vector_store()
