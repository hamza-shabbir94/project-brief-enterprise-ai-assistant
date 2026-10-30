"""
STEP 1 of the RAG pipeline: build the knowledge base.

    PDFs  ->  text  ->  chunks  ->  embeddings  ->  vector store (Pinecone or Chroma)

Run it once (and again whenever the documents change):

    python ingest.py
"""

import bisect
import hashlib
import re

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from vector_store import create_empty_vector_store

load_dotenv()  # reads OPENAI_API_KEY and PINECONE_API_KEY from a .env file (this folder or a parent)


def find_pdfs():
    """All PDFs in the documents folder, skipping macOS junk folders."""
    pdfs = sorted(config.DOCUMENTS_DIR.rglob("*.pdf"))
    return [p for p in pdfs if "__MACOSX" not in p.parts]


def describe_file(path):
    """Build metadata from the file's location and name.

    documents/internal_docs_by_area/HR_policies/IronStore_Remote_Work_Policy.pdf
      -> doc_type="policy", department="HR_policies", title="Remote Work Policy"
    """
    relative = path.relative_to(config.DOCUMENTS_DIR)
    if relative.parts[0] == "product_catalog":
        doc_type, department = "product_catalog", "Products"
    else:
        doc_type, department = "policy", relative.parts[1]

    title = path.stem.replace("IronStore_", "").replace("_", " ")
    return {
        "source": str(relative),
        "title": title,
        "doc_type": doc_type,
        "department": department,
    }


def find_last_reviewed(text):
    """Find dates like 'Last reviewed: August 2026' or 'Last reviewed in December 2021'."""
    match = re.search(r"Last reviewed(?: in|:)?\s*([A-Z][a-z]+ \d{4})", text)
    return match.group(1) if match else "unknown"


def is_outdated(last_reviewed):
    year = re.search(r"\d{4}", last_reviewed)
    return bool(year) and int(year.group()) < config.OUTDATED_BEFORE_YEAR


def load_and_split(path, splitter):
    """Turn one PDF into a list of chunks, each with metadata."""
    pages = PyPDFLoader(str(path)).load()

    # Join all pages into one text, so a product or section that continues
    # on the next page is not cut in half. We remember where each page
    # starts so we can still tell which page a chunk came from.
    page_starts, full_text = [], ""
    for page in pages:
        page_starts.append(len(full_text))
        # The PDFs use an invisible control character (\x7f) as the bullet symbol.
        full_text += page.page_content.replace("\x7f", "•") + "\n"

    metadata = describe_file(path)
    metadata["last_reviewed"] = find_last_reviewed(full_text)
    metadata["outdated"] = is_outdated(metadata["last_reviewed"])

    chunks = splitter.split_documents([Document(page_content=full_text, metadata=metadata)])
    for chunk in chunks:
        start = chunk.metadata.pop("start_index")
        chunk.metadata["page"] = bisect.bisect_right(page_starts, start)  # 1-based
    return chunks


def remove_duplicates(chunks):
    """Drop chunks whose text we've already seen.

    A safety net for the same document being added twice (e.g. a copied PDF).
    Products listed twice *inside* a catalog end up in different chunks, so
    those are handled by the prompt instead (prefer the latest, flag discontinued).
    """
    seen, unique = set(), []
    for chunk in chunks:
        fingerprint = hashlib.md5(" ".join(chunk.page_content.split()).lower().encode()).hexdigest()
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(chunk)
    return unique


def main():
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        add_start_index=True,
    )

    pdfs = find_pdfs()
    print(f"Found {len(pdfs)} PDF files")

    all_chunks = []
    for path in pdfs:
        chunks = load_and_split(path, splitter)
        flag = "  (OUTDATED - will be excluded from answers)" if chunks[0].metadata["outdated"] else ""
        print(f"  {len(chunks):4d} chunks  {path.name}{flag}")
        all_chunks.extend(chunks)

    unique_chunks = remove_duplicates(all_chunks)
    print(f"\n{len(all_chunks)} chunks total, {len(all_chunks) - len(unique_chunks)} duplicates removed")

    print(f"Preparing an empty {config.VECTOR_STORE} vector store...")
    vector_store = create_empty_vector_store()

    batch_size = 500
    for i in range(0, len(unique_chunks), batch_size):
        vector_store.add_documents(unique_chunks[i:i + batch_size])
        print(f"  embedded {min(i + batch_size, len(unique_chunks))}/{len(unique_chunks)}")

    print(f"\nDone. {len(unique_chunks)} chunks stored in {config.VECTOR_STORE}.")


if __name__ == "__main__":
    main()
