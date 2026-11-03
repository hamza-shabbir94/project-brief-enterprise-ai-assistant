"""
The backend: a small web API around rag.py.

    POST /api/chat     {"question": "...", "history": [...]}  ->  {"answer": "...", "sources": [...]}
    GET  /api/health   quick check that the server is running

On Vercel this file runs as a serverless function. Locally, run:

    uvicorn api.index:app --reload --port 8000
"""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from typing import Literal

from pydantic import BaseModel, Field

# rag.py lives one folder up, so make it importable from here.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from rag import ask  # noqa: E402

app = FastAPI(title="IronStore Assistant API")


# --- Request and response shapes -----------------------------------------
# Pydantic checks incoming data for us: an empty or huge question is
# rejected with a 422 error before our code even runs.

class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # Earlier messages in the conversation, so follow-ups like "and for contractors?" work.
    history: list[Turn] = Field(default=[], max_length=50)


class Source(BaseModel):
    number: int
    title: str
    page: int
    department: str
    last_reviewed: str
    score: float
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    search_query: str  # the follow-up rewritten as a standalone question


# --- Endpoints -----------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    try:
        result = ask(question, [turn.model_dump() for turn in request.history])
    except Exception as error:
        print(f"Error answering {question!r}: {error!r}")  # shows up in Vercel's logs
        raise HTTPException(status_code=500, detail="Something went wrong while searching the documents.")

    sources = [
        Source(
            number=i,
            title=doc.metadata["title"],
            page=doc.metadata["page"],
            department=doc.metadata["department"],
            last_reviewed=doc.metadata["last_reviewed"],
            score=doc.metadata["score"],
            excerpt=doc.page_content[:500],
        )
        for i, doc in enumerate(result["sources"], start=1)
    ]
    return ChatResponse(answer=result["answer"], sources=sources, search_query=result["search_query"])
