"""
STEP 3: a chat interface in the browser.

    streamlit run streamlit_app.py
"""

import streamlit as st

from rag import ask

st.set_page_config(page_title="IronStore Assistant", page_icon="🤖")
st.title("🤖 IronStore Enterprise AI Assistant")
st.caption("Ask about company policies, procedures or products. Answers cite the internal documents they come from.")


def show_sources(sources):
    with st.expander(f"Sources ({len(sources)})"):
        for i, doc in enumerate(sources, start=1):
            m = doc.metadata
            st.markdown(f"**[{i}] {m['title']}**, page {m['page']}  \n"
                        f"_{m['department']} · last reviewed {m['last_reviewed']}_")
            st.text(doc.page_content[:400] + ("..." if len(doc.page_content) > 400 else ""))


# Streamlit re-runs this whole file on every interaction, so we keep the
# chat history in st.session_state to remember it between runs.
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Try asking")
    st.markdown(
        "- What is our remote work policy?\n"
        "- How do I request time off?\n"
        "- What is the return policy for customers?\n"
        "- How much does the Nordview NQ-55U7 TV cost?\n"
        "- How do I submit an expense claim?"
    )
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            show_sources(message["sources"])

if question := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching company documents..."):
            result = ask(question)
        st.markdown(result["answer"])
        show_sources(result["sources"])

    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
    )
