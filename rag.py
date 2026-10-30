"""
STEP 2 of the RAG pipeline: answer questions.

    question  ->  retrieve relevant chunks  ->  prompt + chunks  ->  LLM  ->  answer

Try it in the terminal:

    python rag.py
"""

from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
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
- Be clear and concise. Use bullet points or numbered steps for procedures.

Sources:
{context}"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{question}"),
])


@lru_cache  # build these once, then reuse them for every question
def get_retriever():
    return get_vector_store().as_retriever(
        search_kwargs={
            "k": config.TOP_K,
            "filter": {"outdated": False},  # never answer from outdated documents
        }
    )


@lru_cache
def get_chain():
    llm = ChatOpenAI(model=config.CHAT_MODEL, temperature=config.TEMPERATURE)
    return prompt | llm | StrOutputParser()


def format_sources(docs):
    """Number each chunk and label it, so the LLM can cite [1], [2], ..."""
    blocks = []
    for i, doc in enumerate(docs, start=1):
        m = doc.metadata
        header = f"[{i}] {m['title']} (page {m['page']}, last reviewed {m['last_reviewed']})"
        blocks.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


def ask(question):
    """Answer a question. Returns the answer text and the chunks it was based on."""
    docs = get_retriever().invoke(question)
    for doc in docs:
        doc.metadata["page"] = int(doc.metadata["page"])  # Pinecone returns 3 as 3.0
    answer = get_chain().invoke({"context": format_sources(docs), "question": question})
    return {"answer": answer, "sources": docs}


if __name__ == "__main__":
    print("IronStore Assistant (type 'quit' to exit)\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue
        result = ask(question)
        print(f"\nAssistant: {result['answer']}\n")
        for i, doc in enumerate(result["sources"], start=1):
            print(f"  [{i}] {doc.metadata['title']}, page {doc.metadata['page']}")
        print()
