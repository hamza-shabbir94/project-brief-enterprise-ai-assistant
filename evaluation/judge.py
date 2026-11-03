"""
LLM-as-a-judge: a stronger model grades each answer on two questions.

    correctness   Does it say the same thing as the reference answer?  (1-5)
    grounded      Is every fact in it supported by the retrieved sources? (yes/no)
                  A "no" means the assistant hallucinated or used outside knowledge.
"""

from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

import config

JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You grade answers from IronStore's internal assistant, which must answer \
employee questions using only the company documents it retrieved.

Grade CORRECTNESS by comparing the answer with the reference answer:
5 = all key facts of the reference are present and correct
4 = the main fact is correct, a minor detail is missing
3 = partly correct, an important fact is missing or vague
2 = mostly wrong or misleading
1 = wrong, or answers when it should have said it couldn't find the information
If the reference says the assistant should NOT find an answer, give 5 when it clearly says it \
couldn't find the information (suggesting who to ask is good) and 1 when it gives an answer anyway.
Extra correct details beyond the reference are fine. Do not reward length.

Grade GROUNDED: true if every factual claim in the answer is supported by the retrieved sources, \
false if anything is invented or comes from outside knowledge. Saying the information could not \
be found is always grounded."""),
    ("human", """Question: {question}

Reference answer: {reference}

Retrieved sources:
{context}

Assistant's answer:
{answer}"""),
])


class Grade(BaseModel):
    reasoning: str = Field(description="One or two sentences explaining the grades.")
    correctness: int = Field(ge=1, le=5)
    grounded: bool


@lru_cache
def get_judge():
    llm = ChatOpenAI(model=config.JUDGE_MODEL, temperature=0)
    return JUDGE_PROMPT | llm.with_structured_output(Grade)


def grade(question, reference, context, answer):
    return get_judge().invoke({
        "question": question,
        "reference": reference,
        "context": context or "(no sources were retrieved)",
        "answer": answer,
    })
