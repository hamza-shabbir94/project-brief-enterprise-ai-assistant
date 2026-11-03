"""
STEP 2 of the RAG pipeline: answer questions.

    question (+ chat history)
      ->  rewrite follow-ups into a standalone question
      ->  retrieve relevant chunks (drop weak matches)
      ->  prompt + chunks + history  ->  LLM  ->  answer

Try it in the terminal:

    python rag.py
"""

import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

import config
from vector_store import get_vector_store

load_dotenv()

SYSTEM_PROMPT = """You are the IronStore Enterprise AI Assistant. You help IronStore employees \
find information in internal company documents: policies, procedures and the product catalog.

Rules:
- Answer ONLY using the numbered sources below. Do not use outside knowledge.
- Cite the sources you used in square brackets, e.g. [1] or [2][4].
- If the sources do not contain the answer, say clearly that you could not find it in the \
company documents, and suggest who the employee could ask (e.g. their manager, HR, IT Service Desk). \
Never guess or invent policies, numbers, prices or product details.
- Quote numbers exactly as the sources state them. Do not calculate new ones \
(e.g. if a policy says "two office days per week", do not turn that into "three days at home").
- If sources disagree, prefer the most recently reviewed one and mention the difference.
- If a product is marked as discontinued, say so, and mention its replacement SKU if one is given.
- The earlier conversation is only there to understand follow-up questions. Facts in your \
answer must still come from the sources below.
- Be clear and concise. Use bullet points or numbered steps for procedures.

Sources:
{context}"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

# Follow-ups like "and for contractors?" can't be searched on their own, so
# we first turn them into a full question using the conversation so far.
CONDENSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Rewrite the user's latest message as a standalone question that can be understood "
     "without the conversation. Keep product names, SKUs, numbers and policy names. "
     "If it is already standalone, return it unchanged. Return only the question."),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

NOT_FOUND_ANSWER = (
    "I couldn't find information about this in the company documents. "
    "Try rephrasing your question, or ask your manager or the relevant team "
    "(e.g. HR, Finance or the IT Service Desk)."
)


@lru_cache  # build these once, then reuse them for every question
def get_llm():
    return ChatOpenAI(model=config.CHAT_MODEL, temperature=config.TEMPERATURE)


@lru_cache
def get_chain():
    return prompt | get_llm() | StrOutputParser()


@lru_cache
def get_condense_chain():
    return CONDENSE_PROMPT | get_llm() | StrOutputParser()


@lru_cache
def get_store():
    return get_vector_store()


def to_messages(history):
    """[{"role": "user"/"assistant", "content": ...}] -> LangChain chat messages.

    Only the last few messages are kept, and old citations like [2] are removed
    because they point to sources from an earlier answer.
    """
    messages = []
    for turn in (history or [])[-config.HISTORY_MESSAGES:]:
        role = "human" if turn["role"] == "user" else "ai"
        messages.append((role, re.sub(r"\[\d+\]", "", turn["content"])))
    return messages


def standalone_question(question, history):
    if not history:
        return question
    return get_condense_chain().invoke({"history": history, "question": question}).strip()


def retrieve(question, min_relevance=config.MIN_RELEVANCE):
    """The TOP_K most similar chunks from up-to-date documents, without weak matches."""
    results = get_store().similarity_search_with_score(
        question,
        k=config.TOP_K,
        filter={"outdated": False},  # never answer from outdated documents
    )
    docs = []
    for doc, score in results:
        if config.VECTOR_STORE == "chroma":
            score = 1 - score / 2  # Chroma returns a distance; turn it into cosine similarity
        if score < min_relevance:
            continue
        doc.metadata["page"] = int(doc.metadata["page"])  # Pinecone returns 3 as 3.0
        doc.metadata["score"] = round(float(score), 3)
        docs.append(doc)
    return docs


def format_sources(docs):
    """Number each chunk and label it, so the LLM can cite [1], [2], ..."""
    blocks = []
    for i, doc in enumerate(docs, start=1):
        m = doc.metadata
        header = f"[{i}] {m['title']} (page {m['page']}, last reviewed {m['last_reviewed']})"
        blocks.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


def ask(question, history=None):
    """Answer a question, optionally as a follow-up in a conversation.

    history: earlier messages, e.g. [{"role": "user", "content": "..."}, {"role": "assistant", ...}]
    Returns the answer, the chunks it was based on, and the question that was searched for.
    """
    messages = to_messages(history)
    search_query = standalone_question(question, messages)
    docs = retrieve(search_query)
    if not docs:
        # Nothing relevant enough: don't let the LLM guess.
        return {"answer": NOT_FOUND_ANSWER, "sources": [], "search_query": search_query}

    answer = get_chain().invoke({
        "context": format_sources(docs),
        "history": messages,
        "question": question,
    })
    return {"answer": answer, "sources": docs, "search_query": search_query}


if __name__ == "__main__":
    print("IronStore Assistant (type 'quit' to exit)\n")
    history = []
    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue
        result = ask(question, history)
        if result["search_query"] != question:
            print(f"  (searched for: {result['search_query']})")
        print(f"\nAssistant: {result['answer']}\n")
        for i, doc in enumerate(result["sources"], start=1):
            print(f"  [{i}] {doc.metadata['title']}, page {doc.metadata['page']}")
        print()
        history += [{"role": "user", "content": question}, {"role": "assistant", "content": result["answer"]}]
